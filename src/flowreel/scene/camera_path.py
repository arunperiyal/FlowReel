"""Camera tracks between named views (plan Section 8.1).

.. code-block:: yaml

    tracks:
      carve:
        frames: 288
        path: linear                  # or spline (Catmull-Rom through the keys)
        ease: smooth                  # between neighbouring keys; default smooth
        keys:
          - {frame: 0, view: carve_wide}
          - {frame: 218, view: carve_close}

``linear`` blends position, focal point, up vector, view angle and parallel scale
between the two neighbouring keys. ``spline`` bends the position and focal point through
all keys with a uniform Catmull-Rom curve; the other values stay linear. The ease maps the
frame's place between two keys before blending, so each segment starts and ends gently
under ``smooth``. Views of different projection (perspective and parallel) cannot be
blended: the track switches at the later key's frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from flowreel.scene.errors import Checker, ConfigError
from flowreel.scene.views import View
from flowreel.tracks import EASE_NAMES, EASINGS

PATHS = ("linear", "spline")


@dataclass(frozen=True)
class CameraTrack:
    """A camera moving through views. ``frames`` is the track's length, ``keys`` pairs of
    ``(frame, View)`` with strictly increasing frames. Call :meth:`at` for the view."""

    keys: tuple
    path: str = "linear"
    ease: str = "smooth"
    frames: int | None = None

    def at(self, frame: float) -> View:
        """The view at ``frame``; held before the first key and after the last."""
        fr = [k[0] for k in self.keys]
        views = [k[1] for k in self.keys]
        if frame <= fr[0]:
            return views[0]
        if frame >= fr[-1]:
            return views[-1]
        i = int(np.searchsorted(fr, frame, side="right")) - 1
        a, b = views[i], views[i + 1]
        t = EASINGS[self.ease]((frame - fr[i]) / (fr[i + 1] - fr[i]))
        if a.parallel != b.parallel:
            return a if t < 1 else b
        pos, foc = _lerp(a.position, b.position, t), _lerp(a.focal, b.focal, t)
        if self.path == "spline":
            pos = _catmull([v.position for v in views], i, t)
            foc = _catmull([v.focal for v in views], i, t)
        up = _lerp(a.up, b.up, t)
        return View(tuple(pos), tuple(foc), tuple(up), _num(a.view_angle, b.view_angle, t),
                    a.parallel, _num(a.parallel_scale, b.parallel_scale, t))


def _num(x: float, y: float, t: float) -> float:
    return x + (y - x) * t


def _lerp(a, b, t: float) -> np.ndarray:
    return np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * t


def _catmull(points, i: int, t: float) -> np.ndarray:
    """Uniform Catmull-Rom between ``points[i]`` and ``points[i+1]`` (ends repeated)."""
    p = [np.asarray(q, float) for q in points]
    p0, p1, p2 = p[max(i - 1, 0)], p[i], p[i + 1]
    p3 = p[min(i + 2, len(p) - 1)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3)


def parse_track(spec, views: dict[str, View], check: Checker | None = None) -> CameraTrack:
    """Build a :class:`CameraTrack`; every key names a view in ``views``."""
    check = check or Checker()
    spec = check.mapping(spec, ("frames", "path", "ease", "keys"), required=("keys",))
    path = check.at("path").choice(spec.get("path", "linear"), PATHS)
    ease = check.at("ease").choice(spec.get("ease", "smooth"), EASE_NAMES)
    frames = spec.get("frames")
    if frames is not None:
        frames = check.at("frames").integer(frames, minimum=1)
    keys, last = [], None
    for i, item in enumerate(check.at("keys").sequence(spec["keys"], 1)):
        where = check.at("keys", i)
        item = where.mapping(item, ("frame", "view"), required=("frame", "view"))
        frame = where.at("frame").number(item["frame"])
        if last is not None and frame <= last:
            raise where.at("frame").error(f"frames must increase, {frame:g} follows {last:g}")
        last = frame
        where.at("view").choice(item["view"], list(views))
        keys.append((frame, views[item["view"]]))
    return CameraTrack(tuple(keys), path, ease, frames)


def load_tracks(path: str | Path, views: dict[str, View]) -> dict[str, CameraTrack]:
    """Read the ``tracks`` mapping of a ``cameras.yml`` (empty if it has none)."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {getattr(exc, 'problem', exc)}", path) from None
    check = Checker(path)
    raw = data.get("tracks", {}) if isinstance(data, dict) else {}
    raw = check.at("tracks").mapping(raw, list(raw))
    return {name: parse_track(spec, views, check.at("tracks", name)) for name, spec in raw.items()}
