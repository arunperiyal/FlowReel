"""A scene's surfaces saved to files, for the camera editor away from the data
(plan Section 8.3: ``--vtp``).

The data of a long case lives where it was computed, often with no display; the editor
needs a window. So the scene of a few steps is saved where the data is
(:func:`save_shot_surfaces`, ``shot render --save-vtp``), the folder copied to a machine
with a display, and opened there (:class:`SavedScenes`, ``camera edit --vtp DIR``).

Each step is a folder, ``<dir>/step_<NNNNNNNN>/``, holding one ``actor_NNN.vtp`` (or
``.vtu``) per 3D actor of the scene and ``scene.json`` with each actor's look. Colours
are baked: a mesh coloured by a field carries the colours it was drawn with as RGBA in
the array ``flowreel_rgba`` (on points or cells), so the files open without the field's
colour map or range. ``<dir>/scene.json`` holds the shot's first view and background.

What is not kept: 2D actors (text, colour bars) and the lights, which the editor sets as
the shot asks; volume rendering. The surfaces are for framing a view, so they look as
they were drawn, though not to the last pixel.
"""
from __future__ import annotations

import json
from pathlib import Path

from flowreel.scene.views import View

RGBA = "flowreel_rgba"
SCENE_FILE = "scene.json"
LOOK = ("Opacity", "Representation", "LineWidth", "PointSize", "Lighting", "Ambient",
        "Diffuse", "Specular", "SpecularPower", "Interpolation", "RenderPointsAsSpheres",
        "RenderLinesAsTubes", "EdgeVisibility", "BackfaceCulling")


def step_folder(folder: str | Path, step: int) -> Path:
    """Where the surfaces of ``step`` go in ``folder``."""
    return Path(folder) / f"step_{step:08d}"


def save_surfaces(plotter, folder: str | Path) -> int:
    """Save every visible 3D actor of ``plotter`` into ``folder`` (made, emptied of old
    actor files first); returns how many were saved. The plotter must have rendered once
    (colours are made at the first render)."""
    import pyvista as pv
    from vtkmodules.vtkCommonCore import reference
    from vtkmodules.vtkRenderingCore import vtkActor
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("actor_*"):
        old.unlink()
    from flowreel.editor.scenes import _props
    records = []
    for actor in _props(plotter.renderer):        # listed first: saving moves the cursor
        if not isinstance(actor, vtkActor) or not actor.GetVisibility():
            continue
        mapper = actor.GetMapper()
        if mapper is None:
            continue
        upstream = mapper.GetInputAlgorithm()
        if upstream is not None:                 # pyvista's pipeline releases its output
            upstream.Update()
        if mapper.GetInput() is None:
            continue
        mesh = pv.wrap(mapper.GetInput()).copy()
        if mesh.n_points == 0:
            continue
        where = None
        if mapper.GetScalarVisibility():
            was = mapper.GetInterpolateScalarsBeforeMapping()
            mapper.InterpolateScalarsBeforeMappingOff()
            cell = reference(0)
            colours = mapper.MapScalars(mapper.GetInput(), 1.0, cell)
            mapper.SetInterpolateScalarsBeforeMapping(was)
            if colours is not None:
                from vtkmodules.util.numpy_support import vtk_to_numpy
                rgba = vtk_to_numpy(colours).copy()
                where = "cell" if int(cell) else "point"
                (mesh.cell_data if where == "cell" else mesh.point_data)[RGBA] = rgba
        prop = actor.GetProperty()
        name = f"actor_{len(records):03d}" + (".vtp" if isinstance(mesh, pv.PolyData) else ".vtu")
        mesh.save(folder / name)
        records.append({
            "file": name, "colours": where, "colour": list(prop.GetColor()),
            "look": {k: getattr(prop, f"Get{k}")() for k in LOOK},
            "scale": list(actor.GetScale()), "position": list(actor.GetPosition()),
            "orientation": list(actor.GetOrientation()), "origin": list(actor.GetOrigin()),
        })
    (folder / SCENE_FILE).write_text(json.dumps({"actors": records}, indent=1))
    return len(records)


def load_surfaces(plotter, folder: str | Path) -> list:
    """Add the actors saved in ``folder`` to ``plotter``; returns them."""
    import pyvista as pv
    folder = Path(folder)
    try:
        records = json.loads((folder / SCENE_FILE).read_text())["actors"]
    except FileNotFoundError:
        raise FileNotFoundError(f"no saved surfaces in {folder} (no {SCENE_FILE})") from None
    actors = []
    for r in records:
        mesh = pv.read(folder / r["file"])
        if r["colours"]:
            actor = plotter.add_mesh(mesh, scalars=RGBA, rgba=True,
                                     preference=r["colours"], show_scalar_bar=False)
        else:
            actor = plotter.add_mesh(mesh, color=tuple(r["colour"]), show_scalar_bar=False)
        prop = actor.GetProperty()
        for k, v in r["look"].items():
            getattr(prop, f"Set{k}")(v)
        actor.SetScale(*r["scale"])
        actor.SetPosition(*r["position"])
        actor.SetOrientation(*r["orientation"])
        actor.SetOrigin(*r["origin"])
        actors.append(actor)
    return actors


def save_shot_surfaces(shot, folder: str | Path, steps=None, source=None, *, views=None,
                       tracks=None, backend: str = "auto") -> list[int]:
    """Save the scene of ``shot`` (a shot file or :class:`~flowreel.scene.shot.Shot`) at
    each of ``steps`` (default: every step the shot shows) into ``folder``, with the
    shot's first view and background in ``folder/scene.json``; returns the steps saved.
    Each step is drawn off-screen with the layer values of the first frame showing it,
    as the editor draws it, with ``backend`` chosen as for a render (so no display is
    asked for)."""
    import pyvista as pv
    from flowreel.scene import backend as backend_mod
    from flowreel.scene.rendering import _environment
    from flowreel.editor.scenes import ShotScenes
    from flowreel.scene.rendering import Scene
    scenes = ShotScenes(Scene.make(shot, source, views, tracks))
    steps = scenes.steps if steps is None else list(steps)
    unknown = [s for s in steps if s not in scenes.steps]
    if unknown:
        raise ValueError(f"steps {unknown} are not in the shot (its steps: {scenes.steps})")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with _environment(backend_mod.environment(backend_mod.choose(backend))):
        for step in steps:
            plotter = pv.Plotter(off_screen=True, window_size=list(scenes.scene.size))
            try:
                scenes.build(plotter, step)
                plotter.render()
                save_surfaces(plotter, step_folder(folder, step))
            finally:
                plotter.close()
    first = scenes.first_view
    (folder / SCENE_FILE).write_text(json.dumps({
        "first_view": {"position": first.position, "focal": first.focal, "up": first.up,
                       "view_angle": first.view_angle, "parallel": first.parallel,
                       "parallel_scale": first.parallel_scale},
        "background": scenes.scene.shot.background,
        "stretch": None if scenes.stretch is None else list(scenes.stretch),
        "shot": scenes.scene.shot.name}, indent=1))
    return steps


class SavedScenes:
    """The scenes saved in ``folder`` by :func:`save_shot_surfaces`, for the editor
    (the same ``steps``, ``first_view`` and ``build`` as
    :class:`~flowreel.editor.scenes.ShotScenes`)."""

    lights = None

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.steps = sorted(int(p.name.split("_")[1]) for p in self.folder.glob("step_*")
                            if (p / SCENE_FILE).is_file())
        if not self.steps:
            raise FileNotFoundError(f"no saved surfaces in {self.folder} (no step_* folders; "
                                    "save them with 'flowreel shot render SHOT --save-vtp DIR')")
        try:
            info = json.loads((self.folder / SCENE_FILE).read_text())
        except FileNotFoundError:
            info = {}
        v = info.get("first_view")
        self._first = None if v is None else View(
            tuple(v["position"]), tuple(v["focal"]), tuple(v["up"]), v["view_angle"],
            v["parallel"], v["parallel_scale"])
        self.stretch = None if info.get("stretch") is None else tuple(info["stretch"])
        from flowreel.scene.rendering import _background
        raw = info.get("background")
        self.background = None if raw is None else _background(raw)

    @property
    def first_view(self) -> View:
        """The shot's first view, or a view of the first step's surfaces from +z."""
        if self._first is not None:
            return self._first
        import pyvista as pv
        bounds = pv.MultiBlock([pv.read(f) for f in step_folder(self.folder, self.steps[0])
                                .glob("actor_*")]).bounds
        lo, hi = bounds[0::2], bounds[1::2]
        centre = tuple((a + b) / 2 for a, b in zip(lo, hi))
        size = max(b - a for a, b in zip(lo, hi)) or 1.0
        return View((centre[0], centre[1], centre[2] + 2.5 * size), centre)

    def build(self, plotter, step: int) -> None:
        """Add the saved actors of ``step`` to ``plotter``."""
        load_surfaces(plotter, step_folder(self.folder, step))
