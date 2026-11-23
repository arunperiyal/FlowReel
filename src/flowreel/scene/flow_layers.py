"""Layers that draw the flow: ``iso``, ``slice`` and ``body`` (plan Section 7.2).

Every option marked "track" may be a number or keys (docs/guide/shots/tracks.md). Colours are sRGB
hex strings. ``colormap`` is ``fire_ice`` (black at the middle, so weak flow fades into a
black background) or a matplotlib name.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from flowreel.colours import BODY, MUTED, colormap, smoothstep
from flowreel.project.names import is_virtual, require_wall
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
        Option("field", track=False, required=True, doc="field whose level is drawn",
               example="lambda2"),
        Option("level", "number", required=True, doc="value of the surface", example=-1.0),
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
        Option("grow", "number", default=1.0, doc="fraction 0..1 of the surface's extent shown"),
        Option("grey", "number", default=0.0, doc="0..1: blend of the colours to grey_colour"),
        Option("grey_colour", "colour", default=MUTED),
    )

    def surface(self, frame, v: dict):
        """The contour at ``v['level']``, with the wall gap applied.

        It depends on the source, step, crop, field, level, colour field and gap only,
        so the renderer's cache keeps it for a frozen shot (``FrameData.cached``).
        """
        data = frame.data
        if v["wall_gap"] > 0:
            require_wall(data.source, v.get("gap_body"), "iso gap_body")
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
        """Apply the clip plane, then the grow limit.

        ``grow`` is a fraction of the whole surface's extent along ``grow_axis`` (taken
        before the clip), so at 0.5 the surface reaches halfway from its upstream end to
        its downstream end, wherever the flow box ends: the prototype's wake growth.
        """
        bounds = mesh.bounds
        if v.get("clip_axis") and v["clip_active"] and mesh.n_points:
            mesh = _cut(mesh, v["clip_axis"], v["clip_position"], v["clip_keep"])
        if v.get("grow_axis") and v["grow"] < 1 and mesh.n_points:
            k = "xyz".index(v["grow_axis"])
            lo, hi = bounds[2 * k:2 * k + 2]
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
    unit), ``field`` (required), ``range`` (vector track ``[low, high]``: it may sweep,
    since the plane is coloured afresh in every frame) and ``colormap`` as for ``iso``,
    ``opacity`` (track), ``fade_weak`` (``[low, high]``: opacity ramps smoothly from 0 where
    ``|field| <= low`` to 1 where ``|field| >= high``; ``null`` keeps it opaque),
    ``near_wall`` (``[low, high]`` in length unit: opacity ramps from 0 at the body to 1
    at ``high``, the mask of the wall's own layer), ``mask_body`` (body name, default
    all bodies).
    """

    name = "slice"
    needs_flow = True
    options = (
        Option("normal", track=False, required=True, doc="x, y or z", example="x"),
        Option("position", "number", required=True, doc="where the plane cuts, length unit",
               example=0.0),
        Option("field", track=False, required=True, doc="field that colours the plane",
               example="vorticity_x"),
        Option("range", "vector", default=(-1.0, 1.0),
               doc="[low, high] of the colour map; may sweep"),
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
            require_wall(data.source, v.get("mask_body"), "slice mask_body")
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
class Contour(Layer):
    """Lines of a field at chosen values, on a cutting plane through the flow.

    Options: ``normal`` and ``position`` (track) place the plane, as for ``slice``;
    ``field`` (required) is the field the lines follow; ``levels`` is a list of the
    field's values, or a count of levels spread evenly over ``range``, both ends
    included (default 11); ``range`` (vector track ``[low, high]``, default
    ``[-1, 1]``) spaces a count of levels, and spans the colour map, so it may sweep;
    ``colour`` (track) draws every line in one colour, unless ``colormap`` is given, which
    colours each line by its value over ``range``; ``width`` (track, pixels) and
    ``opacity`` (track).
    """

    name = "contour"
    needs_flow = True
    options = (
        Option("normal", track=False, required=True, doc="x, y or z", example="z"),
        Option("position", "number", required=True, doc="where the plane cuts, length unit",
               example=0.0),
        Option("field", track=False, required=True, doc="field the lines follow",
               example="pressure"),
        Option("levels", track=False, default=11,
               doc="a list of values, or a count spread over range"),
        Option("range", "vector", default=(-1.0, 1.0),
               doc="[low, high]: spaces a count of levels and spans the colour map; may sweep"),
        Option("colour", "colour", default="#ffffff"),
        Option("colormap", track=False, default=None,
               doc="colour each line by its value instead of colour"),
        Option("width", "number", default=2.0, doc="line width, pixels"),
        Option("opacity", "number", default=1.0),
    )

    @classmethod
    def check(cls, raw: dict, check) -> None:
        check.at("normal").choice(raw["normal"], ("x", "y", "z"))
        levels = raw.get("levels", 11)
        if isinstance(levels, bool) or not isinstance(levels, (int, list)):
            raise check.at("levels").error(
                f"expected a list of values or a count, got {levels!r}")
        if isinstance(levels, int) and levels < 1:
            raise check.at("levels").error(f"a count must be at least 1, got {levels}")
        if isinstance(levels, list):
            if not levels:
                raise check.at("levels").error("give at least one value")
            for k, value in enumerate(levels):
                check.at("levels", k).number(value)

    @staticmethod
    def level_values(v) -> list[float]:
        """The values the lines are drawn at, for the option values ``v``."""
        levels = v["levels"]
        if isinstance(levels, list):
            return [float(x) for x in levels]
        low, high = v["range"]
        return [float(x) for x in np.linspace(low, high, levels)]

    def mesh(self, frame, v):
        """The lines (``PolyData``) with the field's values on them, or ``None`` when
        no level crosses the plane."""
        data = frame.data
        data.need(v["field"])
        cut = data.flow.slice(normal=v["normal"],
                              origin=_origin(v["normal"], v["position"])).triangulate()
        if not cut.n_points:
            return None
        lines = cut.contour(self.level_values(v), scalars=v["field"])
        return lines if lines.n_points else None

    def draw(self, plotter, frame) -> None:
        v = frame.values
        lines = self.mesh(frame, v)
        if lines is None:
            return
        common = dict(line_width=v["width"], opacity=v["opacity"], lighting=False,
                      show_scalar_bar=False)
        if v.get("colormap"):
            plotter.add_mesh(lines, scalars=v["field"], cmap=colormap(v["colormap"]),
                             clim=list(v["range"]), **common)
        else:
            plotter.add_mesh(lines, color=v["colour"], **common)


SEED_KINDS = ("line", "plane", "round")
_SEED_KEYS = {"line": ("from", "to", "count"),
              "plane": ("normal", "position", "lo", "hi", "counts"),
              "round": ("body", "station", "radius", "count")}


@register
class Streamlines(Layer):
    """Streamlines of the flow, traced from seed points both ways along the velocity.

    Options: ``seeds`` (required), exactly one of ``line: {from: [x, y, z], to: [x, y,
    z], count: N}`` (points spaced evenly, ends included), ``plane: {normal: x|y|z,
    position: P, lo: [a, b], hi: [a, b], counts: [n, m]}`` (a grid on the plane; ``a``
    and ``b`` are the two other axes in x, y, z order) or ``round: {body: NAME, station:
    S, radius: R, count: N}`` (a ring about the body's axis at ``station``, ``radius``
    times its diameter, default 0.75; the body may be left out when there is one);
    ``length`` (length unit; default the flow's diagonal) is how far each line runs each
    way; ``style`` ``lines`` (``width`` in pixels) or ``tubes`` (``radius``, length unit,
    default 0.2 % of the diagonal); ``colour`` (track), or ``field`` with ``range`` and
    ``colormap``; ``opacity`` (track); ``relative`` (default false): traced in the
    velocity relative to the body, which moves at the speed of its centre between the
    saved steps either side, as the section panel's streamlines are. ``true`` takes the
    body and station of ``round`` seeds; with other seeds give ``{body: NAME, station:
    S}``.
    """

    name = "streamlines"
    needs_flow = True
    options = (
        Option("seeds", track=False, required=True, doc="line, plane or round",
               example={"line": {"from": [-1.0, -0.5, 0.0], "to": [-1.0, 0.5, 0.0],
                                 "count": 20}}),
        Option("length", track=False, default=None,
               doc="how far each line runs each way, length unit; default the diagonal"),
        Option("style", "choice", choices=("lines", "tubes"), default="lines"),
        Option("width", "number", default=2.0, doc="line width, pixels"),
        Option("radius", track=False, default=None,
               doc="tube radius, length unit; default 0.2% of the diagonal"),
        Option("colour", "colour", default="#ffffff"),
        Option("field", track=False, default=None, doc="colour the lines by this field"),
        Option("range", "vector", default=(-1.0, 1.0), doc="[low, high] of the colour map"),
        Option("colormap", track=False, default="fire_ice"),
        Option("opacity", "number", default=1.0),
        Option("relative", track=False, default=False,
               doc="relative to the body: true (round seeds) or {body, station}"),
    )

    @classmethod
    def check(cls, raw: dict, check) -> None:
        seeds = check.at("seeds").mapping(raw["seeds"], SEED_KINDS)
        given = [k for k in SEED_KINDS if k in seeds]
        if len(given) != 1:
            raise check.at("seeds").error(f"give exactly one of {', '.join(SEED_KINDS)}")
        kind = given[0]
        at = check.at("seeds", kind)
        spec = at.mapping(seeds[kind], _SEED_KEYS[kind])
        if kind == "line":
            for key in ("from", "to"):
                _point(spec, key, 3, at)
            _count(spec, "count", at)
        elif kind == "plane":
            at.at("normal").choice(spec.get("normal"), ("x", "y", "z"))
            at.at("position").number(spec.get("position"))
            for key in ("lo", "hi"):
                _point(spec, key, 2, at)
            counts = spec.get("counts")
            if not (isinstance(counts, list) and len(counts) == 2):
                raise at.at("counts").error(f"expected [n, m], got {counts!r}")
            for k, n in enumerate(counts):
                if isinstance(n, bool) or not isinstance(n, int) or n < 1:
                    raise at.at("counts", k).error(f"expected a whole number >= 1, got {n!r}")
        else:
            if "station" not in spec:
                raise at.error("'round' needs 'station' (where along the body's axis)")
            at.at("station").number(spec["station"])
            if spec.get("radius") is not None and at.at("radius").number(spec["radius"]) <= 0:
                raise at.at("radius").error("must be positive")
            _count(spec, "count", at)
        for key in ("length", "radius"):
            if raw.get(key) is not None and check.at(key).number(raw[key]) <= 0:
                raise check.at(key).error("must be positive")
        relative = raw.get("relative", False)
        if isinstance(relative, dict):
            rel = check.at("relative").mapping(relative, ("body", "station"))
            if "station" not in rel:
                raise check.at("relative").error("needs 'station' (where to take the body's speed)")
            check.at("relative", "station").number(rel["station"])
        elif not isinstance(relative, bool):
            raise check.at("relative").error(
                f"expected true, false or {{body, station}}, got {relative!r}")
        elif relative and kind != "round":
            raise check.at("relative").error(
                "true takes the body and station of round seeds; give {body: NAME, "
                "station: S} with line or plane seeds")

    @staticmethod
    def _ring(data, spec) -> np.ndarray:
        from flowreel.project.measure import long_axis
        from flowreel.project.names import declaration, one_body
        from flowreel.scene.framing import body_centre
        name = spec.get("body") or one_body(data.source)
        surface = data.body(name)
        body = declaration(data.source, name)
        axis = (body.axis if body else None) or long_axis(surface) or "z"
        station = float(spec["station"])
        slab = 0.25 * body.diameter if body and body.diameter else None
        centre = np.asarray(body_centre(surface, station, axis, slab), float)
        k = "xyz".index(axis)
        if body and body.diameter:
            diameter = body.diameter
        else:                                # measured: the section's width
            from flowreel.project.measure import section
            ring = np.delete(np.asarray(section(surface, station, axis, slab)) - centre, k, 1)
            diameter = 2 * float(np.linalg.norm(ring, axis=1).max())
        r = float(spec.get("radius") or 0.75) * diameter
        n = int(spec.get("count", 24))
        u, v = [i for i in range(3) if i != k]
        angle = np.linspace(0, 2 * np.pi, n, endpoint=False)
        out = np.tile(centre, (n, 1))
        out[:, u] += r * np.cos(angle)
        out[:, v] += r * np.sin(angle)
        return out

    def seed_points(self, data, seeds) -> np.ndarray:
        """The seed points ``(n, 3)`` for the ``seeds`` option, at this frame."""
        kind = next(k for k in SEED_KINDS if k in seeds)
        spec = seeds[kind]
        if kind == "line":
            a, b = np.asarray(spec["from"], float), np.asarray(spec["to"], float)
            t = np.linspace(0, 1, int(spec.get("count", 20)))[:, None]
            return a + t * (b - a)
        if kind == "plane":
            k = "xyz".index(spec["normal"])
            u, v = [i for i in range(3) if i != k]
            (lo_a, lo_b), (hi_a, hi_b) = spec["lo"], spec["hi"]
            n, m = spec["counts"]
            A, B = np.meshgrid(np.linspace(lo_a, hi_a, n), np.linspace(lo_b, hi_b, m))
            out = np.zeros((A.size, 3))
            out[:, k], out[:, u], out[:, v] = float(spec["position"]), A.ravel(), B.ravel()
            return out
        return self._ring(data, spec)

    def _body_speed(self, data, v) -> np.ndarray:
        from flowreel.compose.flow_cut import body_velocity
        from flowreel.project.measure import long_axis
        from flowreel.project.names import declaration, one_body
        relative, seeds = v["relative"], v["seeds"]
        where = seeds["round"] if relative is True else relative
        name = where.get("body") or one_body(data.source)
        body = declaration(data.source, name)
        axis = (body.axis if body else None) or long_axis(data.body(name)) or "z"
        slab = 0.25 * body.diameter if body and body.diameter else None
        return body_velocity(data.source, data.step, name, axis, float(where["station"]), slab)

    def mesh(self, frame, v):
        """The streamlines (``PolyData`` of lines), or ``None`` when none leaves a seed
        inside the flow."""
        import pyvista as pv
        data = frame.data
        data.need("velocity", *([v["field"]] if v.get("field") else []))
        flow = data.flow
        vectors = "velocity"
        if v.get("relative"):
            flow = flow.copy(deep=False)
            flow.point_data["velocity_seen"] = (np.asarray(flow.point_data["velocity"])
                                                - self._body_speed(data, v))
            vectors = "velocity_seen"
        diagonal = float(np.linalg.norm(np.subtract(flow.bounds[1::2], flow.bounds[::2])))
        seeds = pv.PolyData(self.seed_points(data, v["seeds"]))
        lines = flow.streamlines_from_source(
            seeds, vectors=vectors, integration_direction="both",
            max_length=float(v.get("length") or diagonal), initial_step_length=0.2,
            max_step_length=0.25,
            step_unit="cl", max_steps=20000, compute_vorticity=False)
        if not lines.n_lines:
            return None
        if v["style"] == "tubes":
            lines = lines.tube(radius=float(v.get("radius") or 0.002 * diagonal), n_sides=12)
        return lines

    def draw(self, plotter, frame) -> None:
        v = frame.values
        lines = self.mesh(frame, v)
        if lines is None:
            return
        common = dict(opacity=v["opacity"], show_scalar_bar=False)
        if v["style"] == "lines":
            common.update(line_width=v["width"], lighting=False)
        else:
            common.update(smooth_shading=True)
        if v.get("field"):
            plotter.add_mesh(lines, scalars=v["field"], cmap=colormap(v["colormap"]),
                             clim=list(v["range"]), **common)
        else:
            plotter.add_mesh(lines, color=v["colour"], **common)


def _point(spec: dict, key: str, n: int, at) -> None:
    value = spec.get(key)
    if not (isinstance(value, list) and len(value) == n):
        raise at.at(key).error(f"expected {n} numbers, got {value!r}")
    for k, x in enumerate(value):
        at.at(key, k).number(x)


def _count(spec: dict, key: str, at) -> None:
    n = spec.get(key, 1)
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise at.at(key).error(f"expected a whole number >= 1, got {n!r}")


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

    A virtual body (``flowreel.yml``) is drawn as a ghost unless ``style`` says
    otherwise, and a ghost has an outline ``edge_width`` pixels wide in its colour, so it
    reads as modelled, not meshed. A virtual body has no wall: ``field`` on it is an
    error.

    ``amplify`` (track) draws the body's displacement from its shape at ``rest_step``
    (default the source's first saved step) that many times larger, so a vibration of a
    hundredth of a diameter can be seen. It is refused in a shot with flow layers, whose
    flow would no longer fit the body.
    """

    name = "body"
    options = (
        Option("body", track=False, default="all"),
        Option("colour", "colour", default=BODY),
        Option("opacity", "number", default=1.0),
        Option("style", "choice", choices=("solid", "ghost"),
               doc="default solid; ghost for virtual bodies"),
        Option("specular", "number", default=0.4),
        Option("field", track=False),
        Option("range", track=False, default=(-1.0, 1.0)),
        Option("colormap", track=False, default="fire_ice"),
        Option("zero_contour", "boolean", default=False),
        Option("zero_colour", "colour", default="#ffffff"),
        Option("zero_width", "number", default=2.0, pixels=True),
        Option("edge_width", "number", default=1.5, pixels=True, doc="a ghost's outline"),
        Option("amplify", "number", default=1.0, doc="displacement drawn this many times larger"),
        Option("rest_step", track=False, doc="step of the rest shape; default the first saved"),
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
        if name:
            for body in self._names():
                require_wall(data.source, body, f"body field {name!r}")
        if name and name not in surf.point_data:
            data.need(name)
            surf = surf.sample(data.flow, pass_point_data=False)  # copy with the flow's arrays
        return surf

    @classmethod
    def check(cls, raw: dict, check) -> None:
        if raw.get("rest_step") is not None:
            check.at("rest_step").integer(raw["rest_step"])

    def _names(self) -> list:
        spec = self.raw.get("body", "all")
        return spec if isinstance(spec, list) else [None if spec == "all" else spec]

    def style(self, frame) -> str:
        """``solid`` or ``ghost``: as given, else ghost when every body drawn is virtual
        (drawn to look modelled, not meshed), else solid."""
        given = frame.values.get("style")
        if given:
            return given
        virtual = [is_virtual(frame.data.source, n) for n in self._names()]
        return "ghost" if all(virtual) else "solid"

    def amplified(self, frame, surf):
        """``surf`` moved from its rest shape by ``amplify`` times its displacement."""
        amp = frame.values.get("amplify", 1.0)
        if amp == 1.0:
            return surf
        source, spec = frame.data.source, self.raw.get("body", "all")
        rest_step = self.raw.get("rest_step", source.steps()[0])
        names = spec if isinstance(spec, list) else [None if spec == "all" else spec]
        rests = [source.body(rest_step, n) for n in names]
        rest = rests[0] if len(rests) == 1 else rests[0].merge(rests[1:])
        if rest.n_points != surf.n_points:
            raise ValueError(f"body: amplify needs the same surface points at every step; step "
                             f"{rest_step} has {rest.n_points}, step {frame.step} {surf.n_points}")
        out = surf.copy()
        out.points = rest.points + amp * (np.asarray(surf.points) - rest.points)
        return out

    def draw(self, plotter, frame) -> None:
        v = frame.values
        surf = self.amplified(frame, self.surface(frame))
        ghost = self.style(frame) == "ghost"
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
        if ghost:                         # the outline, on top: modelled, not meshed
            plotter.add_silhouette(surf, color=v["colour"], line_width=v["edge_width"],
                                   opacity=v["opacity"], feature_angle=60)
