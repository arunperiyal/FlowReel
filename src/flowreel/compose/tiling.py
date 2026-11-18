"""Draw a layout's composed frames (plan Section 9.1) and skip the ones still fresh.

:func:`layout` writes ``out/<layout>/frame_00000.png`` ... A composed frame has a key
(plan Section 11) from the layout's settings and the path, size and modification time
of every tile frame it shows, so it is drawn again only when a tile's frame was
re-rendered or the layout changed; ``force`` draws every frame again.

Tiles of a ``stations`` entry are rendered first, each station's shot at its tile's
size into ``out/<shot>_station<value>@<W>x<H>/``, through
:func:`flowreel.scene.render`, which skips its own fresh frames.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Iterable

from flowreel.compose.frames import FrameMatch, match
from flowreel.compose.layout_file import Layout, Tile, load, scaled
from flowreel.scene.keys import KeyStore, code_version, digest
from flowreel.scene.rendering import FRAME_NAME, draft_size

PAD = 0.5            # label padding from the tile's edges, in label heights


@dataclass
class ComposeReport:
    """What :func:`layout` did: the output ``folder``, the picture ``size`` and, per
    composed frame asked for, ``(index, path, status)`` with status ``composed`` or
    ``skipped`` (already drawn with the same key)."""

    folder: Path
    size: tuple[int, int]
    frames: list[tuple[int, Path, str]] = field(default_factory=list)

    def count(self, status: str) -> int:
        """Number of frames with ``status``."""
        return sum(f[2] == status for f in self.frames)


def layout(lay, out: str | Path = "frames", *, frames: Iterable[int] | None = None,
           force: bool = False, scale: float | None = None,
           size: tuple[int, int] | None = None,
           progress: Callable[[tuple[int, Path, str]], None] | None = None,
           render: dict | None = None) -> ComposeReport:
    """Compose the frames of ``lay`` (a :class:`~flowreel.compose.Layout` or a layout
    file) into ``out/<name>/frame_00000.png`` ...

    ``frames`` limits the composed frames to those indices (default: every index any
    tile has, :func:`~flowreel.compose.frames.match`). ``scale`` or ``size`` draws a
    draft into ``out/<name>@<W>x<H>/`` (sizes as for shots,
    :func:`~flowreel.scene.rendering.draft_size`). A frame drawn before with the same
    key is skipped unless ``force``. ``progress`` is called with each frame's entry.
    ``render`` holds options for :func:`flowreel.scene.render` of the ``stations``
    tiles (``jobs``, ``backend``, ``processes`` ...); ``force`` applies to them too.
    """
    lay = load(lay) if not isinstance(lay, Layout) else lay
    pic = draft_size(lay.size, scale, size)
    drawn = scaled(lay, pic)
    drawn = render_stations(drawn, out, force=force, **(render or {}))
    m = match(drawn)
    indices = m.indices if frames is None else _chosen(frames, m, lay)
    name = lay.name if pic == tuple(lay.size) else f"{lay.name}@{pic[0]}x{pic[1]}"
    folder = Path(out) / name
    folder.mkdir(parents=True, exist_ok=True)
    store = KeyStore(folder)
    report = ComposeReport(folder, pic)
    for i in indices:
        path = folder / FRAME_NAME.format(i)
        key = frame_key(drawn, m.files[i])
        if not force and store.fresh(path, key):
            entry = (i, path, "skipped")
        else:
            picture = compose_frame(drawn, m.files[i])
            tmp = path.with_name(path.stem + ".part.png")
            picture.save(tmp)
            os.replace(tmp, path)          # a frame file is never half written
            store.put(path.name, key)
            entry = (i, path, "composed")
        report.frames.append(entry)
        if progress:
            progress(entry)
    return report


def _chosen(frames, m: FrameMatch, lay: Layout) -> list[int]:
    from flowreel.scene.errors import Checker
    out = sorted(set(int(i) for i in frames))
    bad = [i for i in out if i not in m.files]
    if bad:
        raise Checker(lay.file).error(f"frame {bad[0]} is not in the layout's tiles "
                                      f"({m.indices[0]}..{m.indices[-1]})")
    return out


def render_stations(lay: Layout, out: str | Path, force: bool = False, **options) -> Layout:
    """Render the shots of ``lay``'s ``stations`` tiles at their tiles' sizes into
    ``out`` and return the layout with those tiles' ``frames`` set to the folders."""
    from flowreel.scene.rendering import render
    tiles = []
    for tile in lay.tiles:
        if tile.shot is not None:
            report = render(tile.shot, out=out, size=tile.size, force=force, **options)
            tile = replace(tile, frames=report.folder)
        tiles.append(tile)
    return replace(lay, tiles=tiles)


def frame_parts(lay: Layout, files: list[Path]) -> dict:
    """What decides a composed frame: the layout's drawn settings and each tile file's
    resolved path, size and modification time."""
    stamps = []
    for f in files:
        st = Path(f).stat()
        stamps.append([str(Path(f).resolve()), st.st_size, st.st_mtime_ns])
    return {"code": code_version("compose"), "size": list(lay.size),
            "background": lay.background,
            "tiles": [{"at": t.at, "size": t.size, "fit": t.fit, "label": t.label,
                       "station": t.station} for t in lay.tiles],
            "files": stamps}


def frame_key(lay: Layout, files: list[Path]) -> str:
    """The key of a composed frame (:func:`frame_parts`); equal keys, equal pictures."""
    return digest(frame_parts(lay, files))


def compose_frame(lay: Layout, files: list[Path]):
    """The composed picture (a PIL RGB image of ``lay.size``) showing ``files[t]`` in
    tile ``t``, tiles drawn in order on the background."""
    from PIL import Image
    picture = Image.new("RGB", lay.size, lay.background)
    for tile, f in zip(lay.tiles, files):
        with Image.open(f) as im:
            frame = im.convert("RGB")
        picture.paste(fitted(frame, tile, lay.background), tile.at)
        if tile.label is not None:
            _label(picture, tile)
    return picture


def fitted(frame, tile: Tile, background: str = "black"):
    """``frame`` resized to fill ``tile.size`` by the tile's ``fit``: ``stretch`` to the
    size, ``contain`` whole and centred on ``background``, ``cover`` filling it with
    the overflow cut evenly from both sides."""
    from PIL import Image
    w, h = tile.size
    if frame.size == (w, h):
        return frame
    if tile.fit == "stretch":
        return frame.resize((w, h), Image.LANCZOS)
    fw, fh = frame.size
    k = (min if tile.fit == "contain" else max)(w / fw, h / fh)
    nw, nh = max(1, round(fw * k)), max(1, round(fh * k))
    frame = frame.resize((nw, nh), Image.LANCZOS)
    if tile.fit == "cover":
        x, y = (nw - w) // 2, (nh - h) // 2
        return frame.crop((x, y, x + w, y + h))
    out = Image.new("RGB", (w, h), background)
    out.paste(frame, ((w - nw) // 2, (h - nh) // 2))
    return out


def _label(picture, tile: Tile) -> None:
    from PIL import ImageDraw, ImageFont

    from flowreel.scene.text import font_file
    lab = tile.label
    font = ImageFont.truetype(font_file(), max(1, round(lab.size)))
    draw = ImageDraw.Draw(picture)
    pad = PAD * lab.size
    (x0, y0), (w, h) = tile.at, tile.size
    right, lower = lab.corner.endswith("right"), lab.corner.startswith("lower")
    x = x0 + w - pad if right else x0 + pad
    y = y0 + h - pad if lower else y0 + pad
    anchor = ("r" if right else "l") + ("s" if lower else "a")   # baseline, or top
    draw.text((x, y), lab.text, fill=lab.colour, font=font, anchor=anchor)
