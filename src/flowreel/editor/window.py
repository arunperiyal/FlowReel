"""The camera editor's window (plan Section 8.3).

A pyvista window showing the shot's scene at one time step. Move the camera with the
mouse as in any VTK window, then:

=====  ===========  =================================================================
Key    Button       Does
=====  ===========  =================================================================
``s``  Save view    the camera's view becomes the track's key at the *Frame* slider's frame
``u``  Undo         goes back one change
``r``  Replace      the key nearest the frame takes the camera's view, keeping its frame
``p``  Play         plays the track, then returns to the view you had
``n``  Next step    shows the next time step (also the *Time step* slider)
=====  ===========  =================================================================

VTK's own meaning of these keys (``s`` surface, ``r`` reset camera, ``u`` user event,
``p`` pick) is switched off in the window; its other keys (``w`` wireframe, ``q`` quit,
...) still work. The line at the top says how many views are saved, the frame and the
step, and what the last key did. Each change is written to ``cameras.yml`` at once
(:class:`~flowreel.editor.state.EditorState`), so the window can be closed at any time.

Points of the model that the film's captions point at can be shown as small markers
with their names (``anchors``), so a view can be framed with room for them.
"""
from __future__ import annotations

import time

from flowreel.editor.scenes import StepCache
from flowreel.editor.state import EditorState
from flowreel.scene.views import View

KEYS = {"s": "save", "u": "undo", "r": "replace", "p": "play", "n": "next_step"}
BUTTONS = (("save", "Save view (s)"), ("undo", "Undo (u)"), ("replace", "Replace (r)"),
           ("play", "Play (p)"), ("next_step", "Next step (n)"))
MARKER = "#ffcc33"           # anchors in the window
TEXT = "#e8e8e8"             # the window's own words, light on the dark scene
PLAY_FPS = 24


class EditorWindow:
    """The editor on ``state`` (an :class:`EditorState`) showing scenes from ``scenes``
    (:class:`~flowreel.editor.scenes.ShotScenes` or
    :class:`~flowreel.editor.surfaces.SavedScenes`).

    ``size`` is the window's size in pixels; ``off_screen`` makes a window that is never
    shown (for tests and scripted sessions: drive it with :meth:`press` and :meth:`look`).
    ``anchors`` are ``(name, (x, y, z))`` points to mark. ``plotter`` is made when not
    given."""

    def __init__(self, state: EditorState, scenes, size=(1280, 720), off_screen: bool = False,
                 anchors=(), plotter=None):
        import pyvista as pv
        self.state, self.scenes = state, scenes
        self.plotter = plotter or pv.Plotter(off_screen=off_screen, window_size=list(size),
                                             title=f"FlowReel camera editor: {state.track}")
        self.message = "move the camera, then s to save a view"
        self._ready = False                 # sliders call back once when made: ignored
        p = self.plotter
        background = getattr(scenes, "background", None)
        if background is not None:
            p.set_background(background)
        self._widgets()
        self.cache = StepCache(p, scenes)
        self.cache.show(state.step)
        first = state.keys[min(state.keys)] if state.keys else scenes.first_view
        self.look(first)
        lights = getattr(scenes, "lights", None)
        if lights is not None:
            from flowreel.scene.lights import apply_lights
            apply_lights(p, lights, first)
        self._markers(anchors)
        self._keys()
        self._ready = True
        self._status()

    # -- the camera -------------------------------------------------------------------

    def view(self) -> View:
        """The camera's view now."""
        c = self.plotter.camera
        return View(tuple(map(float, c.position)), tuple(map(float, c.focal_point)),
                    tuple(map(float, c.up)), float(c.view_angle), bool(c.parallel_projection),
                    float(c.parallel_scale))

    def look(self, view: View) -> None:
        """Put the camera at ``view``."""
        view.apply(self.plotter.camera)
        self.plotter.renderer.ResetCameraClippingRange()

    # -- actions ----------------------------------------------------------------------

    def press(self, key: str) -> bool:
        """Do what key ``key`` does; ``False`` for a key the editor does not take."""
        action = KEYS.get(key)
        if action is None:
            return False
        getattr(self, action)()
        return True

    def save(self) -> None:
        name = self.state.save(self.view())
        self.message = f"saved {name} at frame {self.state.frame}"
        self._status()

    def undo(self) -> None:
        self.message = "undone" if self.state.undo() else "nothing to undo"
        self._status()

    def replace(self) -> None:
        frame = self.state.replace(self.view())
        self.message = ("no view to replace yet: s saves one" if frame is None
                        else f"replaced the view at frame {frame}")
        self._status()

    def play(self) -> None:
        views = self.state.play()
        if not views:
            self.message = "no view saved yet: s saves one"
            self._status()
            return
        here = self.view()
        for v in views:
            self.look(v)
            self.plotter.render()
            if not self.plotter.off_screen:
                time.sleep(1 / PLAY_FPS)
        self.look(here)
        self.message = f"played {len(views)} frames"
        self._status()

    def next_step(self) -> None:
        self._show(self.state.next_step())

    def set_frame(self, value: float) -> None:
        """The *Frame* slider."""
        if not self._ready:
            return
        self.state.set_frame(value)
        if self._frame_slider is not None:       # set from code: move the slider too
            self._frame_slider.GetRepresentation().SetValue(self.state.frame)
        self._status()

    def set_step(self, value: float) -> None:
        """The *Time step* slider: a position in the list of steps."""
        if not self._ready:
            return
        self._show(self.state.set_step(value))

    def show(self) -> None:
        """Open the window and wait until it is closed."""
        self.plotter.show()

    # -- inside -----------------------------------------------------------------------

    def _step_title(self) -> str:
        return f"Time step {self.state.step} ({self.state.step_index + 1} of {len(self.state.steps)})"

    def _show(self, step: int) -> None:
        if self._step_slider is not None:          # keys move the slider too
            rep = self._step_slider.GetRepresentation()
            rep.SetValue(self.state.step_index)
            rep.SetTitleText(self._step_title())
        start = time.perf_counter()
        built = self.cache.show(step)
        self.message = (f"step {step} loaded in {time.perf_counter() - start:.1f} s" if built
                        else f"step {step}")
        self._status()
        self.plotter.render()

    def _status(self) -> None:
        self.plotter.add_text(f"{self.state.status()}\n{self.message}", position="upper_left",
                              font_size=10, color=TEXT, shadow=True, name="status")

    def _widgets(self) -> None:
        p, st = self.plotter, self.state
        self._frame_slider = None
        if st.frames > 1:
            self._frame_slider = p.add_slider_widget(self.set_frame, [0, st.frames - 1], value=st.frame, title="Frame",
                                pointa=(0.05, 0.08), pointb=(0.45, 0.08), fmt="%.0f",
                                style="modern")
        self._step_slider = None
        if len(st.steps) > 1:
            self._step_slider = p.add_slider_widget(
                self.set_step, [0, len(st.steps) - 1], value=st.step_index,
                title=self._step_title(), pointa=(0.55, 0.08), pointb=(0.95, 0.08),
                fmt="%.0f", style="modern")
        width, height = p.window_size
        for k, (action, label) in enumerate(BUTTONS):
            y = height - 90 - 40 * k
            p.add_checkbox_button_widget(lambda _on, a=action: getattr(self, a)(), size=26,
                                         position=(10, y), color_on="#4a6a8a",
                                         color_off="#4a6a8a")
            p.add_text(label, position=(44, y + 4), font_size=9, color=TEXT, shadow=True,
                       name=f"button_{action}")

    def _keys(self) -> None:
        iren = self.plotter.iren.interactor
        style = iren.GetInteractorStyle()

        def on_char(_obj, _event):
            if not self.press(iren.GetKeyCode()):
                style.OnChar()                    # VTK's own keys, but not ours
            self.plotter.render()

        style.AddObserver("CharEvent", on_char)
        self._style, self._iren = style, iren

    def _markers(self, anchors) -> None:
        anchors = list(anchors)
        if not anchors:
            return
        import numpy as np
        points = np.array([a[1] for a in anchors], float)
        stretch = getattr(self.scenes, "stretch", None)
        if stretch is not None:                  # where the stretched model is drawn
            points = points * np.asarray(stretch, float)
        self.plotter.add_point_labels(points, [a[0] for a in anchors], point_color=MARKER,
                                      point_size=10, text_color=MARKER, font_size=11,
                                      shape_opacity=0.3, render_points_as_spheres=True,
                                      always_visible=True, name="anchors")
