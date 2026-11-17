"""The camera of a shot: its ``camera`` mapping turned into a view per frame
(plan Section 7.4; the keys are in docs/cameras.md).

.. code-block:: yaml

    camera: {view: main}                                  # a named view
    camera: {track: carve}                                # a camera track
    camera: {fit: domain, direction_of: main, margin: 1.1}
    camera: {view: close, follow: riser, station: {from: 2, to: 10, frames: [0, 120]},
             axis: x, motion: false}

Exactly one of ``view``, ``track`` and ``fit`` gives the base view; ``follow`` then moves
it onto a body: a body name (declared in ``flowreel.yml`` or a zone of the source), or
``true`` for the one body there is. Views and tracks come from ``cameras.yml`` beside the shot file.
"""
from __future__ import annotations

from pathlib import Path

from flowreel import tracks as tracks_mod
from flowreel.scene.camera_path import CameraTrack, load_tracks
from flowreel.scene.errors import Checker
from flowreel.scene.framing import AXES, body_centre, fit, follow
from flowreel.project.names import declaration, one_body
from flowreel.scene.views import View, load_views

BASES = ("view", "track", "fit")


class ShotCamera:
    """The view of each frame of a shot.

    ``spec`` is the shot's ``camera`` mapping, ``views`` and ``tracks`` the named views
    and camera tracks. :meth:`view` takes the frame index and its
    :class:`~flowreel.scene.layers.FrameData` (``fit`` reads the domain or crop,
    ``follow`` the body). ``rest_step`` is the step whose body ``motion: false``
    follows (the shot's first frame).
    """

    def __init__(self, spec: dict, views: dict[str, View], tracks: dict[str, CameraTrack],
                 check: Checker, rest_step: int | None = None):
        given = [k for k in BASES if k in spec]
        if len(given) != 1:
            raise check.error(f"give exactly one of {', '.join(BASES)}"
                              + (f", got {', '.join(given)}" if given else ""))
        self.base = given[0]
        self.rest_step = rest_step
        self.view_ = self.track = None
        if self.base == "view":
            self.view_ = views[check.at("view").choice(spec["view"], list(views))]
        elif self.base == "track":
            self.track = tracks[check.at("track").choice(spec["track"], list(tracks))]
        else:
            from flowreel.scene.marker_layers import _check_region
            _check_region(spec["fit"], check.at("fit"))
            if "direction_of" not in spec:
                raise check.error("'fit' needs 'direction_of' (the view whose direction it keeps)")
            self.view_ = views[check.at("direction_of").choice(spec["direction_of"], list(views))]
            self.fit = spec["fit"]
            self.margin = check.at("margin").number(spec.get("margin", 1.1))
            if self.margin <= 0:
                raise check.at("margin").error(f"must be positive, got {self.margin:g}")
        for key in ("direction_of", "margin"):
            if key in spec and self.base != "fit":
                raise check.at(key).error("is used only with 'fit'")
        follow_spec = spec.get("follow")
        self.follows = follow_spec is not None and follow_spec is not False
        for key in ("station", "axis", "motion"):
            if key in spec and not self.follows:
                raise check.at(key).error("is used only with 'follow'")
        # follow: NAME, or follow: true for the one body (None: chosen per frame)
        self.body = None if follow_spec is True else follow_spec
        if self.follows:
            if self.body is not None:
                check.at("follow").string(self.body)
            if "station" not in spec:
                raise check.error("'follow' needs 'station' (where along the body)")
            try:
                self.station = tracks_mod.parse(spec["station"], kind="number", name="station")
            except ValueError as exc:
                raise check.at("station").wrap(exc) from None
            self.axis = (None if "axis" not in spec
                         else check.at("axis").choice(spec["axis"], list(AXES)))
            self.motion = spec.get("motion", True)
            if not isinstance(self.motion, bool):
                raise check.at("motion").error(f"expected true or false, got {self.motion!r}")

    def view(self, frame: int, data) -> View:
        """The view at ``frame``."""
        if self.base == "track":
            view = self.track.at(frame)
        elif self.base == "fit":
            from flowreel.scene.marker_layers import region
            view = fit(self.view_, region(self.fit, data), self.margin)
        else:
            view = self.view_
        if self.follows:
            step = data.step if self.motion or self.rest_step is None else self.rest_step
            name = self.body if self.body is not None else one_body(data.source)
            surface = data.source.body(step, name)
            body = declaration(data.source, name)
            axis = self.axis or (body.axis if body else None) or "z"
            slab = 0.25 * body.diameter if body and body.diameter else None
            view = follow(view, body_centre(surface, self.station.at(frame), axis, slab))
        return view

    def key(self, frame: int, data) -> dict:
        """What the camera contributes to the frame key: the view's numbers."""
        v = self.view(frame, data)
        return {"position": v.position, "focal": v.focal, "up": v.up,
                "view_angle": v.view_angle, "parallel": v.parallel,
                "parallel_scale": v.parallel_scale}


def shot_camera(shot, views: dict[str, View] | None = None,
                tracks: dict[str, CameraTrack] | None = None,
                rest_step: int | None = None) -> ShotCamera:
    """The :class:`ShotCamera` of ``shot``.

    ``views`` and ``tracks`` default to those in the ``cameras.yml`` next to the shot
    file. Errors name the shot file and the ``camera`` key.
    """
    check = Checker(shot.file, ("camera",))
    if not shot.camera:
        raise check.error("the shot has no camera (for example camera: {view: main})")
    if views is None:
        if not shot.file:
            raise check.error("no cameras.yml to read the views from (pass views=)")
        path = Path(shot.file).parent / "cameras.yml"
        if not path.exists():
            raise check.error(f"no cameras.yml beside the shot file ({path})")
        views = load_views(path)
        if tracks is None:
            tracks = load_tracks(path, views)
    return ShotCamera(shot.camera, views, tracks or {}, check, rest_step)
