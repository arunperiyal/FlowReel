"""Views: camera frames as flexflow stores them (plan Sections 7.4 and 8.1).

A view has ``position``, ``focal``, ``up``, and either ``view_angle`` (perspective,
vertical field of view in degrees) or ``parallel: true`` with ``parallel_scale`` (half the
frame height in model units). ``cameras.yml``::

    views:
      - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
      - {name: top, position: [6, 40, 9.5], focal: [6, 0, 9.5], up: [0, 0, -1],
         parallel: true, parallel_scale: 10.6}

A file holding one bare view (what ``flexflow field render --pick-camera`` writes) is
also valid. Lengths are in the source's unit.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from flowreel.scene.errors import Checker

VIEW_KEYS = ("name", "position", "focal", "up", "view_angle", "parallel", "parallel_scale")
DEFAULT_ANGLE = 30.0


@dataclass(frozen=True)
class View:
    """One camera frame. Build with :func:`parse_view`; ``replace`` makes variants."""

    position: tuple[float, float, float]
    focal: tuple[float, float, float]
    up: tuple[float, float, float] = (0.0, 1.0, 0.0)
    view_angle: float = DEFAULT_ANGLE
    parallel: bool = False
    parallel_scale: float = 1.0
    name: str = ""

    @property
    def direction(self) -> np.ndarray:
        """Unit vector from the position to the focal point (the viewing direction)."""
        d = np.subtract(self.focal, self.position)
        return d / np.linalg.norm(d)

    @property
    def distance(self) -> float:
        """Distance from the position to the focal point."""
        return float(np.linalg.norm(np.subtract(self.focal, self.position)))

    def with_(self, **changes) -> "View":
        """A copy with some fields changed."""
        return replace(self, **changes)

    def apply(self, camera) -> None:
        """Set a ``pyvista``/VTK camera to this view."""
        camera.position = self.position
        camera.focal_point = self.focal
        camera.up = self.up
        camera.parallel_projection = self.parallel
        if self.parallel:
            camera.parallel_scale = self.parallel_scale
        else:
            camera.view_angle = self.view_angle


def parse_view(spec, check: Checker | None = None) -> View:
    """Build a :class:`View` from a mapping. Errors name the key path."""
    check = check or Checker()
    spec = check.mapping(spec, VIEW_KEYS, required=("position", "focal"))
    pos = check.at("position").numbers(spec["position"], 3)
    focal = check.at("focal").numbers(spec["focal"], 3)
    up = check.at("up").numbers(spec.get("up", (0, 1, 0)), 3)
    if np.allclose(pos, focal):
        raise check.error("position and focal are the same point")
    d = np.subtract(focal, pos)
    if np.linalg.norm(np.cross(d, up)) < 1e-9 * np.linalg.norm(d) * max(np.linalg.norm(up), 1e-300):
        raise check.at("up").error("is zero or parallel to the viewing direction")
    parallel = spec.get("parallel", False)
    if not isinstance(parallel, bool):
        raise check.at("parallel").error(f"expected true or false, got {parallel!r}")
    angle = check.at("view_angle").number(spec.get("view_angle", DEFAULT_ANGLE))
    if not 0 < angle < 180:
        raise check.at("view_angle").error(f"must be between 0 and 180 degrees, got {angle:g}")
    scale = check.at("parallel_scale").number(spec.get("parallel_scale", 1.0))
    if scale <= 0:
        raise check.at("parallel_scale").error(f"must be positive, got {scale:g}")
    if parallel and "parallel_scale" not in spec:
        raise check.error("a parallel view needs 'parallel_scale'")
    return View(pos, focal, up, angle, parallel, scale, str(spec.get("name", "")))


def load_views(path: str | Path) -> dict[str, View]:
    """Read ``cameras.yml``: a ``views`` list (names required), or one bare view.

    Returns the views by name; a bare view is named ``main``. Camera tracks in the
    same file are read by :func:`flowreel.scene.camera_path.load_tracks`.
    """
    path = Path(path)
    from flowreel.yamlfile import read_yaml
    data = read_yaml(path)
    check = Checker(path)
    if isinstance(data, dict) and "position" in data:
        return {"main": parse_view({**data, "name": data.get("name", "main")}, check)}
    if not isinstance(data, dict) or "views" not in data:
        raise check.error("expected a 'views' list or a single view")
    out: dict[str, View] = {}
    for i, item in enumerate(check.at("views").sequence(data["views"], 1)):
        where = check.at("views", i)
        if not isinstance(item, dict) or "name" not in item:
            raise where.error("missing key 'name'")
        view = parse_view(item, where)
        if view.name in out:
            raise where.at("name").error(f"duplicate view name {view.name!r}")
        out[view.name] = view
    return out
