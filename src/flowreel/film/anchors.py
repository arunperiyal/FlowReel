"""Points anchored in the model (plan Section 12): captions and shapes that follow the
camera.

Wherever a caption's ``place`` or a shape's point takes ``[x, y]`` in pixels, it may
instead be a point of the model, projected onto every frame of the film it shows in:

.. code-block:: yaml

    - lines: ['Groove $0.08D$ deep']
      at: [8.4, 10.6]
      place: {model: [6, 0.42, 0.18], offset: [40, -120]}   # text's upper left corner
      shapes:
        - {arrow: {from: {model: [6, 0.42, 0.18], offset: [40, -60]},
                   to: {model: [6, 0.42, 0.18]}, width: 4}}

``model`` is in the source's units. ``offset`` (pixels, ``y`` down) moves the point on
the screen after projection, so a label can sit beside what it names and still follow it.

**Which camera.** By default the camera that drew the frame on screen: ``shot render``
records it with the frames (:mod:`flowreel.scene.frame_views`), so a camera track,
``follow`` or ``fit`` is followed without being repeated here. For frames FlowReel did
not draw, ``view: NAME`` (a fixed view) or ``track: NAME`` (a camera track, at the
frame's number) names a camera of the project's ``cameras.yml``, at its root beside
``flowreel.yml`` (without a project, the one beside the film file).

**Which frame.** Output frame ``j`` of a finished shot shows a position among the shot's
frames (:meth:`~flowreel.film.timeline.TimedShot.positions`); between two frames, as
when frames are interpolated or blended to the film's rate, the point is blended between
its places in the two; under ``to_output: repeat`` it stays with the frame shown, and in
a freeze it stays put. A ``hold_last_of`` shot uses the last frame
of the shot it holds. Cards and layouts have no camera, so a point in the model is an
error there.

**Into the film.** The point's pixel in the drawn frame is carried into the film's
picture as the frame is: scaled to fit and centred (:func:`flowreel.film.clips.fit`).

**Hidden.** A point behind the camera, or outside the drawn picture (before its
``offset``), cannot be shown: its shape is left out of that frame, and a caption whose
``place`` it is shows no text there. ``film check`` lists where (:func:`hidden_spans`).
"""
from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flowreel.scene.errors import Checker

ANCHOR_KEYS = ("model", "offset", "view", "track")
POINT_KEYS = ("from", "to", "centre", "at")       # shape keys that hold a point


@dataclass(frozen=True)
class Anchor:
    """A point of the model: ``model`` ``(x, y, z)``, moved by ``offset`` ``(dx, dy)``
    pixels on screen; ``view`` or ``track`` names the camera (``None``: the frame's own)."""

    model: tuple[float, float, float]
    offset: tuple[float, float] = (0.0, 0.0)
    view: str | None = None
    track: str | None = None


def parse_anchor(value, check: Checker) -> Anchor:
    """An anchor mapping, ``{model: [x, y, z], offset: [dx, dy], view: V | track: T}``."""
    spec = check.mapping(value, ANCHOR_KEYS, required=("model",))
    model = tuple(float(v) for v in check.at("model").numbers(spec["model"], 3))
    offset = tuple(float(v) for v in check.at("offset").numbers(spec.get("offset", (0, 0)), 2))
    if "view" in spec and "track" in spec:
        raise check.error("give 'view' or 'track', not both")
    view = None if spec.get("view") is None else check.at("view").string(spec["view"])
    track = None if spec.get("track") is None else check.at("track").string(spec["track"])
    return Anchor(model, offset, view, track)


def anchored(caption) -> bool:
    """Whether ``caption`` has a point in the model (its place or a shape's)."""
    return isinstance(caption.place, Anchor) or any(
        isinstance(shape.get(k), Anchor) for shape in caption.shapes for k in POINT_KEYS)


def anchors_of(caption) -> list[Anchor]:
    """Every anchor of ``caption``, its place first."""
    out = [caption.place] if isinstance(caption.place, Anchor) else []
    return out + [shape.get(k) for shape in caption.shapes for k in POINT_KEYS
                  if isinstance(shape.get(k), Anchor)]


class ShotProjector:
    """Film pixels of anchors on each output frame of one shot of a film.

    ``film`` is the :class:`~flowreel.film.schema.Film`, ``line`` its timeline, ``name``
    the shot. :meth:`point` gives an anchor's place on output frame ``j``. Raises
    ``ValueError`` for a shot without a camera (a card or a layout), and when a frame
    has no recorded view and the anchor names no ``view`` or ``track``."""

    def __init__(self, film, line, name: str):
        self.film, self.name = film, name
        ts = line.shot(name)
        kind = ts.shot.kind
        if kind == "hold_last_of":
            held = line.shot(ts.shot.source)
            if held.shot.kind != "frames":
                raise ValueError(f"shot {name!r} holds {held.shot.name!r}, a {held.shot.kind}: "
                                 f"a point in the model needs a frames shot")
            self.folder = Path(held.shot.source)
            self.positions = [float(held.order[-1])] * round(ts.length * film.fps)
        elif kind == "frames":
            self.folder = Path(ts.shot.source)
            self.positions = [float(p) for p in ts.positions(film.fps)]
            if ts.shot.rate.to_output == "repeat":      # each frame shown as it is
                self.positions = [float(math.floor(p + 1e-9)) for p in self.positions]
        else:
            raise ValueError(f"shot {name!r} is a {kind}: it has no camera, so a caption on "
                             f"it cannot point at the model (use [x, y] in pixels)")
        from flowreel.scene.frame_views import load_views
        self.record = load_views(self.folder)
        self._cameras = None
        self._sizes: dict[int, tuple[int, int]] = {}

    def point(self, anchor: Anchor, j: int) -> tuple[float, float] | None:
        """Where ``anchor`` is in the film on output frame ``j`` (pixels, ``y`` down), or
        ``None`` when it is hidden there (behind the camera or outside the picture)."""
        pos = self.positions[min(max(j, 0), len(self.positions) - 1)]
        a, frac = int(math.floor(pos)), pos - math.floor(pos)
        first = self._drawn(anchor, a, pos if frac == 0 else a)
        if first is None:
            return None
        if frac > 1e-9:
            second = self._drawn(anchor, a + 1, a + 1)
            if second is None:
                return None
            first = (first[0] + (second[0] - first[0]) * frac,
                     first[1] + (second[1] - first[1]) * frac, first[2])
        x, y, size = first
        sx, sy, ox, oy = fitting(size, self.film.size)
        return (x * sx + ox + anchor.offset[0], y * sy + oy + anchor.offset[1])

    def _drawn(self, anchor: Anchor, index: int, frame: float):
        """``(x, y, size)``: the anchor in frame ``index`` as drawn, or ``None`` if
        hidden. ``frame`` is the frame number a ``track`` is taken at."""
        from flowreel.scene.frame_views import DrawnView
        from flowreel.scene.rendering import FRAME_NAME
        if anchor.view is not None or anchor.track is not None:
            views, tracks = self._named_cameras()
            if anchor.view is not None:
                if anchor.view not in views:
                    raise ValueError(f"no view {anchor.view!r} in {self._cameras_path()} "
                                     f"(views: {', '.join(views) or 'none'})")
                view = views[anchor.view]
            else:
                if anchor.track not in tracks:
                    raise ValueError(f"no camera track {anchor.track!r} in "
                                     f"{self._cameras_path()} (tracks: {', '.join(tracks) or 'none'})")
                view = tracks[anchor.track].at(frame)
            drawn = DrawnView(view, self._size(index))
        else:
            drawn = self.record.get(FRAME_NAME.format(index))
            if drawn is None:
                raise ValueError(
                    f"shot {self.name!r}: {self.folder / FRAME_NAME.format(index)} has no "
                    f"recorded camera (frames drawn by 'flowreel shot render' keep one in "
                    f"{self.folder / '.views.json'}); render it again, or give the anchor "
                    f"'view' or 'track' from the film's cameras.yml")
        x, y, depth = drawn.pixels(anchor.model)[0]
        w, h = drawn.size
        if not (np.isfinite(x) and np.isfinite(y)) or depth <= 0 or not (0 <= x <= w and 0 <= y <= h):
            return None
        return (float(x), float(y), drawn.size)

    def _cameras_path(self) -> Path:
        """The project's ``cameras.yml``, at its root (beside ``flowreel.yml``); without
        a project, the one beside the film file."""
        from flowreel.project import find_project
        found = find_project(self.film.folder)
        return (found.parent if found is not None else self.film.folder) / "cameras.yml"

    def _named_cameras(self):
        if self._cameras is None:
            from flowreel.scene.camera_path import load_tracks
            from flowreel.scene.views import load_views
            path = self._cameras_path()
            if not path.is_file():
                raise ValueError(f"an anchor names a view or track, but there is no {path}")
            views = load_views(path)
            self._cameras = (views, load_tracks(path, views))
        return self._cameras

    def _size(self, index: int) -> tuple[int, int]:
        if index not in self._sizes:
            from PIL import Image
            from flowreel.scene.rendering import FRAME_NAME
            with Image.open(self.folder / FRAME_NAME.format(index)) as im:
                self._sizes[index] = im.size
        return self._sizes[index]


def fitting(drawn: tuple[int, int], film: tuple[int, int]) -> tuple[float, float, float, float]:
    """``(sx, sy, ox, oy)``: a pixel ``(x, y)`` of a picture of size ``drawn`` lands at
    ``(x * sx + ox, y * sy + oy)`` of the film once fitted and centred, as ffmpeg's
    ``scale`` (aspect kept, rounded) and ``pad`` in :func:`flowreel.film.clips.fit` do."""
    (w, h), (fw, fh) = drawn, film
    s = min(fw / w, fh / h)
    iw, ih = round(w * s), round(h * s)
    return iw / w, ih / h, float((fw - iw) // 2), float((fh - ih) // 2)


@dataclass(frozen=True)
class Placed:
    """A caption on one output frame: ``caption`` with every anchor replaced by its film
    pixel, ``text`` whether its words show (its anchored place is not hidden), and
    ``hidden`` the number of its shapes left out."""

    caption: object
    text: bool
    hidden: int


def place(caption, projector: ShotProjector, j: int) -> Placed:
    """``caption`` on output frame ``j`` of ``projector``'s shot (see :class:`Placed`)."""
    text, where = True, caption.place
    if isinstance(where, Anchor):
        p = projector.point(where, j)
        text, where = p is not None, (p if p is not None else (0.0, 0.0))
    shapes, hidden = [], 0
    for shape in caption.shapes:
        keys, ok = dict(shape.keys), True
        for k in POINT_KEYS:
            if isinstance(keys.get(k), Anchor):
                p = projector.point(keys[k], j)
                if p is None:
                    ok = False
                    break
                keys[k] = p
        if ok:
            from flowreel.film.shapes import IN_MODEL
            kind = IN_MODEL.get(shape.kind, shape.kind)
            shapes.append(dataclasses.replace(shape, kind=kind, keys=keys))
        else:
            hidden += 1
    return Placed(dataclasses.replace(caption, place=where, shapes=tuple(shapes)), text, hidden)


@dataclass(frozen=True)
class Hidden:
    """A stretch of film where an anchored caption cannot show all of itself: its
    ``caption``'s first line, the ``shot``, ``start`` and ``end`` in film seconds, and
    ``what`` is hidden (``text``, ``N shapes`` or both)."""

    caption: str
    shot: str
    start: float
    end: float
    what: str

    def message(self) -> str:
        """The warning ``film check`` prints."""
        return (f"caption {self.caption!r} on shot {self.shot!r}: {self.what} hidden from "
                f"{self.start:.2f} to {self.end:.2f} s (behind the camera or off the frame)")


def hidden_spans(clips) -> list[Hidden]:
    """Where the anchored captions of a film are hidden, shot by shot
    (``clips`` is the film's :class:`~flowreel.film.clips.Clips`)."""
    out = []
    fps = clips.film.fps
    for ts in clips.line.shots:
        name = ts.shot.name
        for c, start, end, *_ in clips.captions(name):
            if not anchored(c):
                continue
            run = None
            for j, p in [*clips.placed(name, c, start, end), (None, None)]:
                what = None
                if p is not None:
                    parts = (["text"] if not p.text else []) + (
                        [f"{p.hidden} shape{'s' * (p.hidden != 1)}"] if p.hidden else [])
                    what = " and ".join(parts) or None
                if run is not None and (what != run[1] or j is None):
                    out.append(Hidden(c.lines[0], name, ts.start + run[0] / fps,
                                      ts.start + (run[2] + 1) / fps, run[1]))
                    run = None
                if what is not None:
                    run = [run[0], what, j] if run is not None else [j, what, j]
    return out
