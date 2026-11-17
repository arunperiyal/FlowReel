"""Layers that draw the flow: ``iso``, ``slice`` and ``body`` (plan Section 7.2).

Every option marked "track" may be a number or keys (docs/tracks.md). Colours are sRGB
hex strings. ``colormap`` is ``fire_ice`` (black at the middle, so weak flow fades into a
black background) or a matplotlib name.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from flowreel.colours import BODY, MUTED, colormap, smoothstep
from flowreel.scene.layers import Layer, Option, register
from flowreel.tracks import parse_colour

AXES = ("x", "y", "z")


def _rgb(values, rng, cmap: str):
    low, high = rng
    return colormap(cmap)((np.asarray(values, float) - low) / (high - low))


def _origin(axis: str, position: float):
    o = [0.0, 0.0, 0.0]
    o["xyz".index(axis)] = position
    return o


@register
class Iso(Layer):
    """An isosurface of a field, optionally coloured by another field.

    Options: ``field`` (name, required; derived fields such as ``lambda2`` or ``Q`` are
    computed), ``level`` (track, the field's value), ``colour_by`` (field name; default
    solid ``colour``), ``range`` ([low, high], the values at the two ends of
    ``colormap``), ``colormap``, ``colour`` (track, used without ``colour_by``),
    ``opacity`` (track), ``wall_gap`` (length unit: surface nearer than this to the
    body ``gap_body`` is hidden; it removes the sheath wrapped round a wall, 0 keeps
    all), ``gap_body`` (body name, default all bodies).
    """

    name = "iso"
    needs_flow = True
    options = (
        Option("field", track=False, required=True, doc="field whose level is drawn"),
        Option("level", "number", required=True, doc="value of the surface"),
        Option("colour_by", track=False, doc="field that colours the surface"),
        Option("range", track=False, default=(-1.0, 1.0), doc="[low, high] of the colour map"),
        Option("colormap", track=False, default="fire_ice"),
        Option("colour", "colour", default="#c8ccd0", doc="solid colour without colour_by"),
        Option("opacity", "number", default=1.0),
        Option("wall_gap", "number", default=0.0),
        Option("gap_body", track=False),
        Option("clip_axis", "choice", default=None, choices=AXES,
               doc="axis of the cutting plane"),
        Option("clip_position", "number", default=0.0, doc="where the plane cuts, length unit"),
        Option("clip_keep", "choice", default="below", choices=("below", "above"),
               doc="which side of the plane stays"),
        Option("clip_active", "boolean", default=True, doc="false: the surface is whole"),
        Option("grow_axis", "choice", default=None, choices=AXES,
               doc="axis along which the surface appears"),
        Option("grow", "number", default=1.0, doc="fraction 0..1 of the flow's extent shown"),
        Option("grey", "number", default=0.0, doc="0..1: blend of the colours to grey_colour"),
        Option("grey_colour", "colour", default=MUTED),
    )

    def surface(self, frame, v: dict):
        """The contour at ``v['level']``, with the wall gap applied (cacheable by the
        renderer: it depends on source, step, field, level and gap only)."""
        data = frame.data
        wanted = [v["field"]] + ([v["colour_by"]] if v.get("colour_by") else [])
        data.need(*wanted)
        mesh = data.flow.contour([v["level"]], scalars=v["field"])
        if v["wall_gap"] > 0 and mesh.n_points:
            wall = data.body(v.get("gap_body"))
            mesh["gap"] = cKDTree(wall.points).query(mesh.points)[0]
            mesh = mesh.clip_scalar(scalars="gap", value=v["wall_gap"], invert=False)
        return mesh

    def draw(self, plotter, frame) -> None:
        v = frame.values
        mesh = self.surface(frame, v)
        if not mesh.n_points:
            return
        mesh = self.finish(mesh, v, frame)
        if not mesh.n_points:
            return
        if v.get("colour_by"):
            rgb = _rgb(mesh[v["colour_by"]], v["range"], v["colormap"])[:, :3]
        else:
            rgb = np.tile(v["colour"], (mesh.n_points, 1))
        mesh["rgb"] = (self.grey(rgb, v) * 255).astype(np.uint8)
        plotter.add_mesh(mesh, scalars="rgb", rgb=True, smooth_shading=True, specular=0.3,
                         ambient=0.25, opacity=v["opacity"], show_scalar_bar=False)

    def finish(self, mesh, v, frame):
        """Apply the clip plane, then the grow limit."""
        if v.get("clip_axis") and v["clip_active"] and mesh.n_points:
            mesh = _cut(mesh, v["clip_axis"], v["clip_position"], v["clip_keep"])
        if v.get("grow_axis") and v["grow"] < 1 and mesh.n_points:
            k = "xyz".index(v["grow_axis"])
            lo, hi = frame.data.flow.bounds[2 * k:2 * k + 2]
            mesh = _cut(mesh, v["grow_axis"], lo + v["grow"] * (hi - lo), "below") \
                if v["grow"] > 0 else _empty(mesh)
        return mesh

    def grey(self, rgb, v):
        """Blend the colours towards ``grey_colour`` by ``grey``."""
        g = v["grey"]
        return rgb if g == 0 else (1 - g) * rgb + g * np.asarray(v["grey_colour"])


def _empty(mesh):
    import pyvista as pv
    return pv.PolyData()


def _cut(mesh, axis: str, position: float, keep: str):
    """Keep the part of ``mesh`` on one side of the plane ``axis = position``."""
    return mesh.clip(axis, origin=_origin(axis, position), invert=(keep == "below"))
