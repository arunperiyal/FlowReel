"""Writing ``cameras.yml`` (plan Sections 8.1 and 8.3).

:func:`save_cameras` writes views and camera tracks in the layout people write by hand,
one view a line and each track with its keys, so a file the camera editor or a camera
command wrote reads as if typed::

    # Written by FlowReel; comments are not kept when it is written again.
    views:
      - {name: main, position: [-19, 13, -5], focal: [6, 0, 8.5], up: [0, 1, 0], view_angle: 30}
    tracks:
      carve:
        frames: 288
        path: linear
        ease: smooth
        keys:
          - {frame: 0, view: carve_wide}

The file reads back equal through :func:`~flowreel.scene.views.load_views` and
:func:`~flowreel.scene.camera_path.load_tracks`: numbers are written with as many digits
as they need to come back the same. The file it replaces is kept as ``cameras.yml.bak``,
and the new file is written beside it and moved into place, so a crash never leaves half
a file. Comments in the old file are not carried over (the first line says so); keep
notes in another file and ``include:`` it if they matter.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from flowreel.scene.camera_path import CameraTrack
from flowreel.scene.views import DEFAULT_ANGLE, View

HEADER = "# Written by FlowReel; comments are not kept when it is written again.\n"


def save_cameras(path: str | Path, views: dict[str, View],
                 tracks: dict[str, CameraTrack] | None = None) -> Path:
    """Write ``views`` and ``tracks`` to ``path`` as a ``cameras.yml``.

    ``views`` maps names to views (each view's ``name`` is taken from its key). Every
    track key's view must be one of ``views``, found by its name; a key whose view is
    not there (or differs from the one of that name) raises ``ValueError``, since the
    file could not say which view it is. An existing file is kept as ``<path>.bak``.
    Returns the path written.
    """
    path = Path(path)
    if not views:
        raise ValueError("no views to write: cameras.yml needs at least one")
    text = HEADER + "views:\n"
    for name, view in views.items():
        text += f"  - {view_line(view.with_(name=name))}\n"
    if tracks:
        text += "tracks:\n"
        for name, track in tracks.items():
            text += _track_text(name, track, views)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)
    return path


def update_cameras(path: str | Path, views: dict[str, View] | None = None,
                   tracks: dict[str, CameraTrack] | None = None) -> Path:
    """Add ``views`` and ``tracks`` to the ``cameras.yml`` at ``path`` (made if missing),
    replacing those of the same names and keeping the rest in their order. Returns the
    path written; see :func:`save_cameras`."""
    from flowreel.scene.camera_path import load_tracks
    from flowreel.scene.views import load_views
    path = Path(path)
    old_views = load_views(path) if path.exists() else {}
    old_tracks = load_tracks(path, old_views) if path.exists() else {}
    return save_cameras(path, {**old_views, **(views or {})}, {**old_tracks, **(tracks or {})})


def view_line(view: View) -> str:
    """One view as a YAML flow mapping, as ``cameras.yml`` lists it. ``view_angle`` is
    left out of a parallel view that has the default, ``parallel_scale`` out of a
    perspective view that has the default (1)."""
    parts = [f"name: {_scalar(view.name)}"] if view.name else []
    parts += [f"position: {_vec(view.position)}", f"focal: {_vec(view.focal)}",
              f"up: {_vec(view.up)}"]
    if not view.parallel or view.view_angle != DEFAULT_ANGLE:
        parts.append(f"view_angle: {_num(view.view_angle)}")
    if view.parallel:
        parts.append("parallel: true")
    if view.parallel or view.parallel_scale != 1.0:
        parts.append(f"parallel_scale: {_num(view.parallel_scale)}")
    return "{" + ", ".join(parts) + "}"


def _track_text(track_name: str, track: CameraTrack, views: dict[str, View]) -> str:
    text = f"  {_scalar(track_name)}:\n"
    if track.frames is not None:
        text += f"    frames: {track.frames}\n"
    text += f"    path: {track.path}\n    ease: {track.ease}\n    keys:\n"
    for i, key in enumerate(track.keys):
        frame, view = key
        name = _name_of(view, views)
        if name is None:
            raise ValueError(f"track {track_name!r}, key {i} (frame {_num(frame)}): its "
                             f"view is not one of the views written"
                             + (f" (none named {view.name!r} is the same)" if view.name else ""))
        entry = f"frame: {_num(frame)}, view: {_scalar(name)}"
        if track.eases and track.eases[i] is not None:
            entry += f", ease: {track.eases[i]}"
        text += f"      - {{{entry}}}\n"
    return text


def _name_of(view: View, views: dict[str, View]) -> str | None:
    """The name under which ``view`` is in ``views``: its own name if that entry is the
    same view, else the first entry equal to it apart from the name."""
    if view.name in views and views[view.name].with_(name="") == view.with_(name=""):
        return view.name
    for name, other in views.items():
        if other.with_(name="") == view.with_(name=""):
            return name
    return None


def _num(x: float) -> str:
    x = float(x)
    if x == int(x) and abs(x) < 1e15:
        return str(int(x))
    text = repr(x)
    if "e" in text and "." not in text:       # YAML 1.1 reads 2e-07 as a string
        mantissa, exponent = text.split("e")
        text = f"{mantissa}.0e{exponent}"
    return text


def _vec(v) -> str:
    return "[" + ", ".join(_num(x) for x in v) + "]"


def _scalar(s: str) -> str:
    """A name as YAML writes it in a flow mapping (quoted when it must be)."""
    out = yaml.safe_dump(str(s), default_flow_style=True, width=1 << 20).strip()
    if out.endswith("\n...") or out.endswith("..."):
        out = out.rsplit("\n", 1)[0].strip()
    if any(c in out for c in ",{}[]") and not out.startswith(("'", '"')):
        out = "'" + out.replace("'", "''") + "'"
    return out
