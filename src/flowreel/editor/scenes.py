"""The scene the camera editor shows, built once per time step (plan Section 8.3).

The window shows one time step at a time. The first time a step is shown its actors are
made, from the data (:class:`ShotScenes`, the shot's layers as ``shot render`` draws
them) or from surfaces saved where the data is (:class:`SavedScenes`); they are kept,
so going back to a step costs nothing. :class:`StepCache` swaps a step's actors in and
out of the window's renderer.

Each scene source gives ``steps`` (the time steps it can show), ``first_view`` (the
camera to open with) and ``build(plotter, step)``, which adds that step's actors.
"""
from __future__ import annotations

from flowreel.scene.views import View


class ShotScenes:
    """The scenes of a shot from its data: ``scene`` is a
    :class:`~flowreel.scene.rendering.Scene`. A step is drawn with the layer values of
    the first frame that shows it (frame 0's for a step the shot never shows)."""

    def __init__(self, scene):
        self.scene = scene
        plan = scene.plan
        self.frame_of: dict[int, int] = {}
        for i in range(plan.n_frames):
            self.frame_of.setdefault(plan.time.step(i), i)
        self.steps = sorted(self.frame_of)

    @property
    def first_view(self) -> View:
        """The shot's camera at its first frame."""
        return self.scene.camera.view(0, self.scene.data(0))

    @property
    def stretch(self):
        """The shot's stretch ``(x, y, z)``, or ``None``."""
        st = self.scene.shot.stretch
        return None if st is None else tuple(st.scale)

    @property
    def lights(self):
        """The shot's lights (``None``: VTK's light kit)."""
        return self.scene.shot.lights

    @property
    def background(self):
        """The shot's background colour, as the renderer takes it."""
        from flowreel.scene.rendering import _background
        return _background(self.scene.shot.background)

    def build(self, plotter, step: int) -> None:
        """Add the actors of ``step`` to ``plotter``."""
        self.scene.populate(plotter, self.frame_of.get(step, 0), step=step)


class StepCache:
    """The actors of each step shown so far, swapped in and out of ``plotter``'s renderer.

    ``source`` is a :class:`ShotScenes` or a :class:`~flowreel.editor.surfaces.SavedScenes`.
    """

    def __init__(self, plotter, source):
        self.plotter, self.source = plotter, source
        self.actors: dict[int, list] = {}
        self.shown: int | None = None

    def show(self, step: int) -> bool:
        """Show ``step``; returns ``True`` when it was built now (first time)."""
        if step == self.shown:
            return False
        renderer = self.plotter.renderer
        if self.shown is not None:
            for actor in self.actors[self.shown]:
                renderer.RemoveActor(actor)
        built = step not in self.actors
        if built:
            before = set(_props(renderer))
            self.source.build(self.plotter, step)
            self.actors[step] = [a for a in _props(renderer) if a not in before]
        else:
            for actor in self.actors[step]:
                renderer.AddActor(actor)
        self.shown = step
        return built


def _props(renderer) -> list:
    """Every prop of ``renderer``, 3D and 2D."""
    props = renderer.GetViewProps()
    props.InitTraversal()
    return [props.GetNextProp() for _ in range(props.GetNumberOfItems())]
