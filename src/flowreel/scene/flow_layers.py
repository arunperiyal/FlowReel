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
        """The contour at ``v['level']``, with the wall gap applied.

        It depends on the source, step, crop, field, level, colour field and gap only,
        so the renderer's cache keeps it for a frozen shot (``FrameData.cached``). The
        flow's bounds go with it as field data ``flow_bounds``, for ``grow``.
        """
        data = frame.data
        parts = {"layer": "iso", **{k: v.get(k) for k in
                                    ("field", "level", "colour_by", "wall_gap", "gap_body")}}

        def build():
            wanted = [v["field"]] + ([v["colour_by"]] if v.get("colour_by") else [])
            data.need(*wanted)
            mesh = data.flow.contour([v["level"]], scalars=v["field"])
            if v["wall_gap"] > 0 and mesh.n_points:
                wall = data.body(v.get("gap_body"))
                mesh["gap"] = cKDTree(wall.points).query(mesh.points)[0]
                mesh = mesh.clip_scalar(scalars="gap", value=v["wall_gap"], invert=False)
            mesh.field_data["flow_bounds"] = np.asarray(data.flow.bounds, float)
            return mesh

        return data.cached(parts, build)

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
        mesh["rgb"] = np.rint(self.grey(rgb, v) * 255).astype(np.uint8)
        plotter.add_mesh(mesh, scalars="rgb", rgb=True, smooth_shading=True, specular=0.3,
                         ambient=0.25, opacity=v["opacity"], show_scalar_bar=False)

    def finish(self, mesh, v, frame):
        """Apply the clip plane, then the grow limit (along the flow's extent)."""
        bounds = mesh.field_data["flow_bounds"] if "flow_bounds" in mesh.field_data else None
        if v.get("clip_axis") and v["clip_active"] and mesh.n_points:
            mesh = _cut(mesh, v["clip_axis"], v["clip_position"], v["clip_keep"])
        if v.get("grow_axis") and v["grow"] < 1 and mesh.n_points:
            k = "xyz".index(v["grow_axis"])
            lo, hi = (frame.data.flow.bounds if bounds is None else bounds)[2 * k:2 * k + 2]
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


@register
class Slice(Layer):
    """A cutting plane through the flow, coloured by a field and faded where it is weak.

    Options: ``normal`` (``x``, ``y`` or ``z``, required), ``position`` (track, length
    unit), ``field`` (required), ``range`` and ``colormap`` as for ``iso``, ``opacity``
    (track), ``fade_weak`` (``[low, high]``: opacity ramps smoothly from 0 where
    ``|field| <= low`` to 1 where ``|field| >= high``; ``null`` keeps it opaque),
    ``near_wall`` (``[low, high]`` in length unit: opacity ramps from 0 at the body to 1
    at ``high``, the mask of the wall's own layer), ``mask_body`` (body name, default
    all bodies).
    """

    name = "slice"
    needs_flow = True
    options = (
        Option("normal", track=False, required=True, doc="x, y or z"),
        Option("position", "number", required=True),
        Option("field", track=False, required=True),
        Option("range", track=False, default=(-1.0, 1.0)),
        Option("colormap", track=False, default="fire_ice"),
        Option("opacity", "number", default=1.0),
        Option("fade_weak", track=False, default=None),
        Option("near_wall", track=False, default=None),
        Option("mask_body", track=False),
    )

    def mesh(self, frame, v):
        """The section as triangles with an ``rgba`` array (uint8), or ``None`` if empty."""
        data = frame.data
        data.need(v["field"])
        cut = data.flow.slice(normal=v["normal"],
                              origin=_origin(v["normal"], v["position"])).triangulate()
        if not cut.n_points:
            return None
        value = np.asarray(cut[v["field"]])
        rgba = _rgb(value, v["range"], v["colormap"])
        alpha = np.full(len(value), float(v["opacity"]))
        if v.get("fade_weak"):
            alpha = alpha * smoothstep(np.abs(value), *v["fade_weak"])
        if v.get("near_wall"):
            wall = data.body(v.get("mask_body")).triangulate()
            dist = cut.compute_implicit_distance(wall)["implicit_distance"]
            alpha = alpha * smoothstep(np.abs(dist), *v["near_wall"])
        rgba[:, 3] = alpha
        cut["rgba"] = np.rint(rgba * 255).astype(np.uint8)
        return cut

    def draw(self, plotter, frame) -> None:
        cut = self.mesh(frame, frame.values)
        if cut is not None:
            plotter.add_mesh(cut, scalars="rgba", rgb=True, lighting=False,
                             show_scalar_bar=False)


@register
class BodyLayer(Layer):
    """One wall surface, a list of them, or all, drawn solid or as a ghost.

    Options: ``body`` (a name, a list of names, or ``all``; default ``all``), ``colour``
    and ``opacity`` (tracks), ``style`` (``solid``; ``ghost`` draws the body see-through
    at a third of its opacity and without highlights, so the flow shows through it),
    ``specular`` (track), ``field`` (colour the surface by this field instead: an array
    already on the surface, or a derived field computed on the flow and sampled onto the
    surface), ``range`` and ``colormap`` for ``field``, ``zero_contour`` (boolean track:
    draw the line where ``field`` is 0, such as separation in wall shear) with
    ``zero_colour`` and ``zero_width`` (pixels, track).
    """

    name = "body"
    options = (
        Option("body", track=False, default="all"),
        Option("colour", "colour", default=BODY),
        Option("opacity", "number", default=1.0),
        Option("style", "choice", default="solid", choices=("solid", "ghost")),
        Option("specular", "number", default=0.4),
        Option("field", track=False),
        Option("range", track=False, default=(-1.0, 1.0)),
        Option("colormap", track=False, default="fire_ice"),
        Option("zero_contour", "boolean", default=False),
        Option("zero_colour", "colour", default="#ffffff"),
        Option("zero_width", "number", default=2.0),
    )
    needs_flow = False

    def surface(self, frame):
        """The wall surface(s) this layer draws, with ``field`` as point data if asked."""
        data, spec = frame.data, self.raw.get("body", "all")
        if isinstance(spec, list):
            meshes = [data.body(n) for n in spec]
            surf = meshes[0] if len(meshes) == 1 else meshes[0].merge(meshes[1:])
        else:
            surf = data.body(None if spec == "all" else spec)
        name = self.raw.get("field")
        if name and name not in surf.point_data:
            data.need(name)
            surf = surf.sample(data.flow, pass_point_data=False)  # copy with the flow's arrays
        return surf

    def draw(self, plotter, frame) -> None:
        v = frame.values
        surf = self.surface(frame)
        ghost = v["style"] == "ghost"
        opacity = v["opacity"] / 3 if ghost else v["opacity"]
        common = dict(smooth_shading=True, split_sharp_edges=True, opacity=opacity,
                      specular=0 if ghost else v["specular"], specular_power=20, ambient=0.25)
        if v.get("field"):
            plotter.add_mesh(surf, scalars=v["field"], cmap=colormap(v["colormap"]),
                             clim=list(v["range"]), show_scalar_bar=False, **common)
            if v["zero_contour"]:
                line = surf.contour([0.0], scalars=v["field"])
                if line.n_points:
                    plotter.add_mesh(line, color=v["zero_colour"], line_width=v["zero_width"],
                                     lighting=False)
        else:
            plotter.add_mesh(surf, color=v["colour"], **common)
