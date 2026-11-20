"""A film's clips (plan Sections 10.2, 10.3, 10.8 and 11): each shot encoded once.

Every shot becomes a **base clip**: its picture alone, at the film's rate and size,
exactly as long as the timeline says. Then a **finished clip**: the base clip with its
fades, captions, shapes and the film's watermark on top. The film is the finished clips
joined (branch 5).

**Rates.** A frames shot plays its frames in the timeline's ``order`` (frozen frames
repeated) at its own ``fps``; ``to_output`` makes up the film's rate:

- ``interpolate``: ffmpeg's ``minterpolate``, motion-compensated, scene-cut detection off
  (a sudden change in the flow is not a cut);
- ``repeat``: each frame shown ``film fps / fps`` times (``fps``), for frames redrawn
  each time, such as streamlines, that interpolation would smear;
- ``blend``: neighbouring frames cross-faded (``framerate``).

Each frame lasts ``ratio = film fps / fps`` output frames, and the last is held for its
whole step (``tpad``), so the clip has ``n * ratio`` frames, ``n / fps`` seconds, as the
timeline plans; output frame ``j`` shows position ``j / ratio`` among the shot's frames,
as :meth:`~flowreel.film.timeline.TimedShot.positions` tells the live plots.
``minterpolate`` never outputs its last input frame, so that frame is given twice: the
motion then reaches it. (The prototype's interpolated shots stopped one flow frame short
and ended early; their planned lengths are unchanged.)

**Layouts.** A layout shot is composed for its output frames
(:func:`flowreel.compose.layout` with ``output``): its flow frames, without the
``rate: output`` panels, are brought to the film's rate like a frames shot, and each
such panel, drawn once per output frame at the time between the flow frames around it,
is laid on top where its tile sits. Interpolation never smears a plot's dot or line.

**Size and colour.** Pictures are scaled to fit the film's size and centred on black
(none is cropped), and converted to BT.709, the colours a player expects of HD video.
Every clip is encoded alike (H.264, yuv420p, the film's rate and time base), so the
film can join them without re-encoding.

**Keys.** A clip's file name holds a key made of everything that changes it: for a
frames shot each frame file's name, size and modification time, the order, the rate and
the whole ffmpeg command; for a card or a hold the drawn picture itself. A clip whose
key exists is used as it is; changing a caption rebuilds the finished clip only, never
the base clip under it.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.film import ffmpeg as ff
from flowreel.film.timeline import EPS
from flowreel.scene.keys import digest
from flowreel.scene.rendering import FRAME_NAME

#: Bumped when this module changes how clips are made, so old clips are rebuilt.
VERSION = 1
SMOOTH = "minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:vsbmc=1:scd=none"
BASE_QUALITY = ("-crf", "10", "-preset", "medium")      # the picture, encoded once
FINISHED_QUALITY = ("-crf", "14", "-preset", "slow")    # the AFMS film's


@dataclass(frozen=True)
class Clip:
    """A clip: its ``path``, the ``shot`` it is of, its ``key``, its ``frames`` at the
    film's rate, and whether it was ``built`` now (``False``: found, with its key)."""

    path: Path
    shot: str
    key: str
    frames: int
    built: bool


def encode_args(fps: int) -> list[str]:
    """The encoding every clip shares, so the film joins them without re-encoding."""
    return ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(fps), "-fps_mode", "cfr",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-video_track_timescale", str(fps * 1000)]


def fit(size: tuple[int, int]) -> str:
    """Filters that fit a picture into ``size`` (width, height), centred on black, in
    BT.709 colours."""
    w, h = size
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease:out_color_matrix=bt709:"
            f"out_range=tv,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1")


def rate_filter(fps: float, film_fps: int, to_output: str) -> str:
    """The filters that bring frames at ``fps`` to the film's ``film_fps`` (see the
    module), ending on the last frame held for a whole step."""
    ratio = round(film_fps / fps)
    if ratio == 1:
        return "null"
    # minterpolate never outputs its last input frame; given it twice, it reaches it.
    step = {"interpolate": f"tpad=stop_mode=clone:stop=1,{SMOOTH.format(fps=film_fps)}",
            "repeat": f"fps={film_fps}", "blend": f"framerate=fps={film_fps}"}[to_output]
    return f"{step},tpad=stop_mode=clone:stop={ratio}"


def stamp(path: Path) -> list:
    """A file's name, size and modification time: a redrawn frame changes its key."""
    st = path.stat()
    return [path.name, st.st_size, st.st_mtime_ns]


@dataclass
class Clips:
    """The clips of one film, kept in ``folder`` (default ``clips/`` beside the film
    file).

    ``film`` is a :class:`~flowreel.film.Film`, ``line`` its
    :class:`~flowreel.film.timeline.Timeline` (laid out when left out). ``force``
    rebuilds every clip asked for. ``panels`` are options for drawing a layout's
    ``rate: output`` panels (:func:`flowreel.compose.layout`, such as ``jobs``)."""

    film: object
    line: object = None
    folder: Path | None = None
    force: bool = False
    panels: dict = field(default_factory=dict)

    def __post_init__(self):
        from flowreel.film.timeline import timeline
        if self.line is None:
            self.line = timeline(self.film)
        self.folder = Path(self.folder) if self.folder is not None else self.film.folder / "clips"
        self.folder.mkdir(parents=True, exist_ok=True)
        self._base: dict[str, Clip] = {}
        self._layouts: dict[str, object] = {}

    # -- shared ------------------------------------------------------------------------

    def _frames(self, ts) -> int:
        return round(ts.length * self.film.fps)

    def _encode(self, kind: str, name: str, parts: dict, inputs: list, chain: str,
                frames: int, quality, prepare=None) -> Clip:
        """Encode ``inputs`` through ``chain`` (a filter graph ending in ``[out]``) into
        ``<kind>_<name>_<key>.mp4``, unless a clip with that key is there. ``prepare``
        is called first when the clip is built (to draw the pictures it reads)."""
        args = [*inputs, "-filter_complex", chain, "-map", "[out]", "-frames:v", frames,
                *encode_args(self.film.fps), *quality]
        key = digest({**parts, "version": VERSION, "args": [str(a) for a in args],
                      "size": list(self.film.size)})[:16]
        path = self.folder / f"{kind}_{name}_{key}.mp4"
        if path.exists() and not self.force:
            return Clip(path, name, key, frames, False)
        for old in self.folder.glob(f"{kind}_{name}_*.mp4"):
            old.unlink()
        if prepare is not None:
            prepare()
        tmp = path.with_name(path.stem + ".part.mp4")
        ff.run(*args, tmp)
        os.replace(tmp, path)
        return Clip(path, name, key, frames, True)

    def _sequence(self, name: str, files: list[Path]) -> Path:
        """A folder of links to ``files`` in playing order, ``frame_00000.png`` ...,
        for ffmpeg to read as one numbered sequence."""
        folder = self.folder / f"sequence_{name}"
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        for i, f in enumerate(files):
            (folder / FRAME_NAME.format(i)).symlink_to(f.resolve())
        return folder

    def _order_files(self, ts, folder: Path) -> list[Path]:
        """The frame files of ``ts`` in playing order, from ``folder``."""
        files = []
        for i in ts.order:
            path = Path(folder) / FRAME_NAME.format(i)
            if not path.is_file():
                raise FileNotFoundError(f"shot {ts.shot.name!r}: frame {path} is missing")
            files.append(path)
        return files

    # -- base clips --------------------------------------------------------------------

    def base(self, name: str) -> Clip:
        """The base clip of shot ``name``: its picture at the film's rate and size,
        built unless one with its key is kept."""
        if name not in self._base:
            ts = self.line.shot(name)
            kind = ts.shot.kind
            self._base[name] = getattr(self, f"_base_{kind}")(ts)
        return self._base[name]

    def _base_frames(self, ts) -> Clip:
        shot = ts.shot
        files = self._order_files(ts, shot.source)
        seq = self._sequence(shot.name, files)
        rate = rate_filter(ts.fps, self.film.fps, shot.rate.to_output)
        chain = f"[0:v]{rate},{fit(self.film.size)}[out]"
        parts = {"kind": "frames", "order": ts.order, "fps": ts.fps,
                 "files": [stamp(f) for f in sorted(set(files))]}
        inputs = ["-framerate", ts.fps, "-i", seq / "frame_%05d.png"]
        return self._encode("base", shot.name, parts, inputs, chain, self._frames(ts),
                            BASE_QUALITY)

    def layout(self, name: str):
        """The :class:`~flowreel.compose.tiling.ComposeReport` of layout shot ``name``,
        composed for its output frames: its flow frames without the ``rate: output``
        panels, and those panels drawn once per output frame (``overlays``). Kept in
        ``<folder>/layouts/``."""
        if name not in self._layouts:
            from flowreel import compose
            ts = self.line.shot(name)
            self._layouts[name] = compose.layout(
                ts.shot.source, self.folder / "layouts", output=ts.positions(self.film.fps),
                force=self.force, panels=self.panels)
        return self._layouts[name]

    def _base_layout(self, ts) -> Clip:
        shot = ts.shot
        report = self.layout(shot.name)
        if not report.frames:
            raise ValueError(f"shot {shot.name!r}: layout {shot.source} has only rate: output "
                             "panels; it needs a tile of flow frames to time them by")
        files = self._order_files(ts, report.folder)
        seq = self._sequence(shot.name, files)
        n = self._frames(ts)
        inputs = ["-framerate", ts.fps, "-i", seq / "frame_%05d.png"]
        rate = rate_filter(ts.fps, self.film.fps, shot.rate.to_output)
        graph, last = [f"[0:v]{rate}[f0]"], "f0"
        panels = []
        for k, (tile, drawn) in enumerate(report.overlays, start=1):
            folder = Path(drawn.folder)
            found = [folder / FRAME_NAME.format(j) for j in range(n)]
            if not all(f.is_file() for f in found):
                raise FileNotFoundError(f"shot {shot.name!r}: panel frames missing in {folder}")
            inputs += ["-framerate", self.film.fps, "-i", folder / "frame_%05d.png"]
            x, y = (round(v) for v in tile.at)
            graph.append(f"[{last}][{k}:v]overlay={x}:{y}:eof_action=repeat[f{k}]")
            last = f"f{k}"
            panels.append([str(folder), [stamp(f) for f in found]])
        graph.append(f"[{last}]{fit(self.film.size)}[out]")
        parts = {"kind": "layout", "order": ts.order, "fps": ts.fps,
                 "files": [stamp(f) for f in sorted(set(files))], "panels": panels}
        return self._encode("base", shot.name, parts, inputs, ";".join(graph), n, BASE_QUALITY)

    def _still(self, ts, image, parts: dict) -> Clip:
        """A clip of ``image`` (Pillow) held for the whole of shot ``ts``, keyed by its
        pixels."""
        import hashlib
        image = image.convert("RGB")
        png = self.folder / f"still_{ts.shot.name}.png"
        image.save(png)
        pixels = hashlib.sha256(image.tobytes()).hexdigest()
        inputs = ["-loop", 1, "-framerate", self.film.fps, "-i", png]
        chain = f"[0:v]{fit(self.film.size)}[out]"
        return self._encode("base", ts.shot.name, {**parts, "pixels": pixels,
                                                   "picture": list(image.size)},
                            inputs, chain, self._frames(ts), BASE_QUALITY)

    def _base_card(self, ts) -> Clip:
        from flowreel.film.cards import card_image, load_card
        image = card_image(load_card(ts.shot.source), self.film.style, self.film.size)
        return self._still(ts, image, {"kind": "card"})

    def _base_hold(self, ts) -> Clip:
        image = self.last_frame(ts.shot.source, overlays=ts.shot.overlays)
        return self._still(ts, image, {"kind": "hold"})

    def last_frame(self, name: str, overlays: bool = True):
        """The last frame shot ``name`` shows, as a Pillow image: its last frame file,
        or for a layout its last composed frame with, when ``overlays``, its
        ``rate: output`` panels as drawn for its last output frame."""
        from PIL import Image
        ts = self.line.shot(name)
        last = FRAME_NAME.format(ts.order[-1])
        if ts.shot.kind == "frames":
            return Image.open(Path(ts.shot.source) / last).convert("RGB")
        report = self.layout(name)
        image = Image.open(report.folder / last).convert("RGB")
        if overlays:
            final = FRAME_NAME.format(self._frames(ts) - 1)
            for tile, drawn in report.overlays:
                panel = Image.open(Path(drawn.folder) / final).convert("RGB")
                image.paste(panel, tuple(round(v) for v in tile.at))
        return image

    # -- finished clips ----------------------------------------------------------------

    def captions(self, name: str) -> list[tuple]:
        """The captions on shot ``name``: ``(caption, start, end, fade_in, fade_out)``
        with ``start`` and ``end`` in seconds of the finished shot. A caption running
        across a cut is cut there without a fade, and fades only where it begins and
        ends."""
        ts = self.line.shot(name)
        out = []
        for tc in self.line.captions_on(name):
            start, end = tc.start - ts.start, tc.end - ts.start
            out.append((tc.caption, max(0.0, start), min(ts.length, end), start > EPS,
                        end < ts.length - EPS))
        return out

    def finished(self, name: str) -> Clip:
        """The finished clip of shot ``name``: its base clip faded in and out, then its
        captions (with their shapes) and the film's watermark laid on top, so text can
        sit on black."""
        from flowreel.film.watermark import key_fields, spans
        ts = self.line.shot(name)
        base = self.base(name)
        n = self._frames(ts)
        fade_in, fade_out = ts.shot.fade
        picture = []
        if fade_in:
            picture.append(f"fade=in:st=0:d={fade_in:g}")
        if fade_out:
            at = ts.shot.fade_out_at if ts.shot.fade_out_at is not None else ts.length - fade_out
            picture.append(f"fade=out:st={at:g}:d={fade_out:g}")
        graph, last = [f"[0:v]{','.join(picture) or 'null'}[v0]"], "v0"
        inputs = ["-i", base.path]
        style = self.film.style
        laid, drawn = [], []
        for k, (c, start, end, fi, fo) in enumerate(self.captions(name)):
            png = self.folder / f"caption_{name}_{k}.png"
            fade = min(c.fade if c.fade is not None else style.caption.fade, (end - start) / 2)
            alpha = []
            if fi and fade > 0:
                alpha.append(f"fade=in:st={start:g}:d={fade:g}:alpha=1")
            if fo and fade > 0:
                alpha.append(f"fade=out:st={end - fade:g}:d={fade:g}:alpha=1")
            last = self._lay(graph, inputs, last, png, alpha, f"between(t,{start:g},{end:g})",
                             ts.length)
            laid.append([c, start, end, fi, fo, fade])
            drawn.append((c, png))
        mark = self.film.watermark
        showing = [(a, b) for shot, a, b in spans(mark, self.line) if shot == name]
        mark_png = self.folder / f"watermark_{name}.png"
        if showing:
            when = "+".join(f"between(t,{a:g},{b:g})" for a, b in showing)
            last = self._lay(graph, inputs, last, mark_png, [], when, ts.length)
        graph.append(f"[{last}]null[out]")
        parts = {"kind": "finished", "base": base.key, "captions": laid, "style": style,
                 "watermark": key_fields(mark) if showing else None, "showing": showing}

        def prepare():
            from flowreel.film.draw import save_caption
            for c, png in drawn:
                save_caption(c, style, self.film.size, png)
            if showing:
                from flowreel.film.watermark import watermark_image
                watermark_image(mark, self.film.size).save(mark_png)

        return self._encode("shot", name, parts, inputs, ";".join(graph), n,
                            FINISHED_QUALITY, prepare)

    def _lay(self, graph: list, inputs: list, last: str, png: Path, alpha: list, when: str,
             length: float) -> str:
        """Lay the transparent picture ``png`` over ``last`` while ``when`` holds,
        through the ``alpha`` fades; returns the new last label."""
        k = len([a for a in inputs if a == "-i"])
        inputs += ["-loop", 1, "-framerate", self.film.fps, "-t", f"{length:g}", "-i", png]
        # In BT.709, as the picture under it, so a caption keeps its colour.
        chain = ",".join(["format=rgba", *alpha, "scale=out_color_matrix=bt709:out_range=tv",
                          "format=yuva420p"])
        graph.append(f"[{k}:v]{chain}[c{k}]")
        graph.append(f"[{last}][c{k}]overlay=0:0:enable='{when}':eof_action=pass[v{k}]")
        return f"v{k}"
