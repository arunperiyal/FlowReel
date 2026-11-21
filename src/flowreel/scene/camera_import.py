"""Views from other programs' files (plan Section 8.2, ``camera import``).

:func:`import_view` reads one camera and returns it as a named
:class:`~flowreel.scene.views.View`, to add to ``cameras.yml`` with
:func:`~flowreel.scene.camera_file.update_cameras`. The kind of file is told by its
extension:

- ``.pvsm``: a ParaView state (*File > Save State*), XML. The camera of a ``RenderView``
  proxy: ``CameraPosition``, ``CameraFocalPoint``, ``CameraViewUp``, ``CameraViewAngle``,
  ``CameraParallelProjection``, ``CameraParallelScale``.
- ``.py``: a ParaView Python state or trace, with lines such as
  ``renderView1.CameraPosition = [-19.0, 13.0, -5.0]``.
- ``.yml`` / ``.yaml``: a flexflow camera frame (``flexflow field render
  --pick-camera``), or any ``cameras.yml``, whose view of that name (or only view) is
  taken.

Numbers are taken as they are: ParaView and flexflow use the same camera as FlowReel
(VTK's), so the view looks the same. FlowReel reads these files itself (plan Section 14:
no dependency on flexflow or ParaView).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from flowreel.scene.errors import Checker
from flowreel.scene.views import parse_view, View

#: ParaView's property names, and the view keys they become.
PROPERTIES = {"CameraPosition": "position", "CameraFocalPoint": "focal",
              "CameraViewUp": "up", "CameraViewAngle": "view_angle",
              "CameraParallelProjection": "parallel", "CameraParallelScale": "parallel_scale"}
VECTORS = ("CameraPosition", "CameraFocalPoint", "CameraViewUp")
SUFFIXES = (".pvsm", ".py", ".yml", ".yaml")


def import_view(path: str | Path, name: str = "main", index: int = 0,
                view: str | None = None) -> View:
    """The camera in ``path`` as a view named ``name``.

    ``index`` picks among several render views of a ParaView state (0, the first, by
    default; in a ``.py`` file, in the order their camera is first set). ``view`` picks a
    view of a ``cameras.yml`` by name (needed when it has more than one). Raises
    :class:`~flowreel.scene.errors.ConfigError` naming the file when it holds no usable
    camera.
    """
    path = Path(path)
    check = Checker(path)
    suffix = path.suffix.lower()
    if suffix not in SUFFIXES:
        raise check.error(f"cannot tell the kind of file from {path.suffix or 'no extension'!r}"
                          f" (expected {', '.join(SUFFIXES)})")
    if not path.is_file():
        raise check.error("no such file")
    if suffix == ".pvsm":
        cameras = _pvsm(path, check)
    elif suffix == ".py":
        cameras = _python(path.read_text(errors="replace"))
    else:
        return _yaml(path, name, view, check)
    if not cameras:
        raise check.error("no render view camera found (no CameraPosition)")
    if not 0 <= index < len(cameras):
        raise check.error(f"view index {index} is out of range: the file has "
                          f"{len(cameras)} render view{'s' * (len(cameras) != 1)}")
    spec = {"name": name}
    for prop, values in cameras[index].items():
        if prop not in PROPERTIES or not values:
            continue
        key = PROPERTIES[prop]
        if prop in VECTORS:
            spec[key] = [float(v) for v in values[:3]]
        elif key == "parallel":
            spec[key] = bool(int(float(values[0])))
        else:
            spec[key] = float(values[0])
    if "position" not in spec or "focal" not in spec:
        raise check.error(f"render view {index} has no CameraPosition or CameraFocalPoint")
    if not spec.get("parallel"):
        spec.pop("parallel_scale", None)        # unused by a perspective view
    return parse_view(spec, check.at(f"render view {index}"))


def _pvsm(path: Path, check: Checker) -> list[dict]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise check.error(f"not a ParaView state: {exc}") from None
    out = []
    for proxy in root.iter("Proxy"):
        if proxy.get("group") != "views" or "RenderView" not in (proxy.get("type") or ""):
            continue
        props = {p.get("name"): [e.get("value") for e in p.findall("Element")]
                 for p in proxy.findall("Property") if p.get("name") in PROPERTIES}
        if props.get("CameraPosition"):
            out.append(props)
    return out


_ASSIGN = re.compile(r"^\s*(\w+)\.(Camera\w+)\s*=\s*(.+?)\s*(?:#.*)?$", re.M)


def _python(text: str) -> list[dict]:
    cameras: dict[str, dict] = {}
    for var, prop, value in _ASSIGN.findall(text):
        if prop not in PROPERTIES:
            continue
        numbers = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", value)
        if value.strip() in ("True", "False"):
            numbers = ["1" if value.strip() == "True" else "0"]
        if numbers:
            cameras.setdefault(var, {})[prop] = numbers      # a later line wins
    return [c for c in cameras.values() if "CameraPosition" in c]


def _yaml(path: Path, name: str, view: str | None, check: Checker) -> View:
    from flowreel.scene.views import load_views
    views = load_views(path)
    if view is None:
        if len(views) != 1:
            raise check.error(f"name the view to take: the file has {', '.join(views)}")
        view = next(iter(views))
    if view not in views:
        raise check.error(f"no view named {view!r} (views: {', '.join(views)})")
    return views[view].with_(name=name)
