"""One shot at several stations of a long body (plan Sections 5.6 and 9.1).

A ``stations`` entry of a layout tiles one shot rendered at several stations along a
body. The shot must move with a station: its crop travels with a body
(``crop: {around: ...}``) or its camera follows one (``camera: {follow: ...}``). The
copy of the shot for one station has that station, fixed, in the crop's ``around``
and in the camera's ``station`` (when the camera gives its own), and the name
``<shot>_station<value>``, so each station renders into its own frame folder.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from flowreel import tracks as tracks_mod
from flowreel.scene.errors import Checker, ConfigError

DEFAULT_LABEL = "station {station:g}"


def read_shot(path: Path, check: Checker):
    """The shot file at ``path``; a missing file or a bad shot is an error at ``check``'s
    key path that also names the shot's own error."""
    from flowreel.scene.shot import load
    if not path.is_file():
        raise check.error(f"no shot file {path}")
    try:
        return load(path)
    except ConfigError as exc:
        raise check.error(f"the shot does not load: {exc}") from None


def at_station(shot, station: float, check: Checker):
    """A copy of ``shot`` whose crop and camera stand at ``station`` (fixed)."""
    from flowreel.scene.shot import CropAround
    track = tracks_mod.parse(station, kind="number", name="station")
    crop, camera = shot.crop, dict(shot.camera)
    moved = False
    if isinstance(crop, CropAround):
        crop, moved = CropAround(crop.body, track, crop.half), True
    follows = camera.get("follow") not in (None, False)
    if follows and "station" in camera:
        camera["station"], moved = station, True
    elif follows and isinstance(crop, CropAround):
        moved = True                 # the camera takes the crop's station
    if not moved:
        raise check.error(f"shot {shot.name!r} neither crops around a body nor follows one, "
                          "so a station does not move it; give it 'crop: {around: ...}' or "
                          "'camera: {follow: ..., station: ...}'")
    return replace(shot, name=f"{shot.name}_station{station:g}", crop=crop, camera=camera)
