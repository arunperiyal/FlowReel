"""The reveal look, drawn from a source, the derived fields and tracks.

A wake surface coloured by vorticity; a cutting plane sweeps along the span, showing a
live section of the flow, while the wake ahead of the plane is cut away and the rest
turns grey. This is ``--look reveal`` of the prototype's ``render_frames.py``, with the
prototype's constants turned into arguments and its progress ramps into tracks.

It is the first end-to-end path through FlowReel (source, fields, tracks, picture) and
the reference for Phase 2, where the wake, the slice and the body become scene layers
and this module becomes a shot file.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv
import yaml
from matplotlib.colors import to_rgb
from scipy.spatial import cKDTree

from flowreel import fields, sources, tracks
from flowreel.box import Box
from flowreel.colours import BODY, FIRE_ICE, MUTED


def _smoothstep(value, start, end):
    """0 below ``start``, 1 above ``end``, smooth between (arrays)."""
    t = np.clip((np.asarray(value, dtype=float) - start) / (end - start), 0, 1)
    return t * t * (3 - 2 * t)


def reveal_frame(source, step: int, frame: float, *, sweep, slice_strength=1.0, grey=0.0,
                 wake_field: str = "lambda2", wake_level: float = -1.0,
                 wall_gap: float = 0.4, colour_field: str = "vorticity_x",
                 colour_range=(-2.5, 2.5), muted=MUTED, axis: str = "x",
                 camera, view_angle: float = 30.0, size=(1920, 1080),
                 crop: Box | None = None, body: str | None = None) -> np.ndarray:
    """Draw one frame of the reveal look; returns the picture, ``(height, width, 3)`` uint8.

    Arguments:
        source: a :class:`~flowreel.sources.Source` with velocity and a body.
        step: the saved step to draw.
        frame: the frame number the tracks are read at.
        sweep: track of the cutting plane's position along ``axis`` (length unit).
        slice_strength: track of the section's opacity, 0 to 1.
        grey: track of how far the wake has turned to ``muted``, 0 to 1.
        wake_field, wake_level: the field and level of the wake surface (lambda2 is
            negative inside vortices).
        wall_gap: the wake nearer than this to the body is hidden (length unit); it
            removes the sheath of high rotation wrapped around the wall.
        colour_field, colour_range: what colours the wake and the section, and the values
            at the two ends of the colour map (black at the middle).
        muted: the colour the wake turns to.
        axis: ``"x"``, ``"y"`` or ``"z"``, the direction the plane travels along.
        camera: ``[position, focal point, view up]``.
        view_angle: vertical field of view in degrees.
        size: ``(width, height)`` in pixels.
        crop: box of the flow to read; default all of it.
        body: name of the body to draw; default every body.

    Tracks are given as their specs (docs/tracks.md) or as numbers. Before the sweep's
    first key the wake is whole; from then on it is cut at the plane.
    """
    sweep = tracks.parse(sweep, kind="number", name="sweep")
    position = sweep.at(frame)
    strength = tracks.parse(slice_strength, kind="number", name="slice_strength").at(frame)
    greyness = tracks.parse(grey, kind="number", name="grey").at(frame)
    started = frame > sweep.frames[0]
    origin = [0.0, 0.0, 0.0]
    origin["xyz".index(axis)] = position

    flow = source.flow(step, ["U", "V", "W"], crop)
    for name, values in fields.compute(flow, [wake_field, colour_field]).items():
        flow.point_data[name] = values
    wall = source.body(step, body)

    wake = flow.contour([wake_level], scalars=wake_field)
    wake["gap"] = cKDTree(wall.points).query(wake.points)[0]
    wake = wake.clip_scalar(scalars="gap", value=wall_gap, invert=False)
    if started:
        wake = wake.clip(axis, origin=origin, invert=False)
    low, high = colour_range

    plot = pv.Plotter(off_screen=True, window_size=list(size))
    plot.set_background("black")
    plot.camera_position = [tuple(v) for v in camera]
    plot.camera.view_angle = view_angle
    plot.enable_anti_aliasing("ssaa")
    plot.add_mesh(wall, color=BODY, smooth_shading=True, split_sharp_edges=True,
                  specular=0.4, specular_power=20, ambient=0.25)

    # The section: transparent where the flow is weak and next to the body.
    cut = flow.slice(normal=axis, origin=origin).triangulate()
    if cut.n_points:
        cut = cut.compute_implicit_distance(wall.triangulate())
        value = np.asarray(cut[colour_field])
        rgba = FIRE_ICE((value - low) / (high - low))
        rgba[:, 3] = (_smoothstep(np.abs(value), 0.05, 0.5)
                      * _smoothstep(np.abs(cut["implicit_distance"]), 0.03, 0.1) * strength)
        cut["rgba"] = (rgba * 255).astype(np.uint8)
        plot.add_mesh(cut, scalars="rgba", rgb=True, lighting=False, show_scalar_bar=False)

    if wake.n_points:
        colour = FIRE_ICE((np.asarray(wake[colour_field]) - low) / (high - low))[:, :3]
        colour = (1 - greyness) * colour + greyness * np.array(to_rgb(muted))
        wake["rgb"] = (colour * 255).astype(np.uint8)
        plot.add_mesh(wake, scalars="rgb", rgb=True, smooth_shading=True, specular=0.3,
                      ambient=0.25, show_scalar_bar=False)

    image = plot.screenshot(return_img=True)
    plot.close()
    return np.asarray(image)[:, :, :3]


def render_shot(path, frame: float | None = None) -> np.ndarray:
    """Draw the reveal shot described by the YAML file at ``path``.

    Keys: ``source`` (``adapter`` plus the adapter's options; ``path`` and ``body`` are
    relative to the file), ``step``, ``frame``, ``size``, ``camera``, ``view_angle``,
    ``wake`` (``field``, ``level``, ``wall_gap``), ``colour`` (``field``, ``range``),
    ``muted``, ``axis``, and the tracks ``sweep``, ``slice_strength`` and ``grey``.
    ``frame`` overrides the file's.
    """
    path = Path(path)
    shot = yaml.safe_load(path.read_text())
    options = dict(shot["source"])
    adapter = options.pop("adapter")
    for key in ("path", "body"):
        if isinstance(options.get(key), str):
            options[key] = str(path.parent / options[key])
    source = sources.create(adapter, **options)
    wake, colour = shot.get("wake", {}), shot.get("colour", {})
    optional = {"wake_field": wake.get("field"), "wake_level": wake.get("level"),
                "wall_gap": wake.get("wall_gap"), "colour_field": colour.get("field"),
                "colour_range": colour.get("range"), "muted": shot.get("muted"),
                "axis": shot.get("axis"), "view_angle": shot.get("view_angle"),
                "size": shot.get("size"), "slice_strength": shot.get("slice_strength"),
                "grey": shot.get("grey")}
    return reveal_frame(source, shot["step"], shot["frame"] if frame is None else frame,
                        sweep=shot["sweep"], camera=shot["camera"],
                        **{k: v for k, v in optional.items() if v is not None})
