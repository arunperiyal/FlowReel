"""The scene design window (plan Section 19.11): a matplotlib window on one scene's layout.

The scene is drawn as the build draws it at the *Time* slider's moment (its boxes'
contents: shots' frames, panels, pictures, text), with each box's outline and name over
it. With the mouse:

- **drag on empty space** to draw a new box (a text box, to be filled);
- **drag a box** to move it; **drag a corner** of the selected box to resize it;
- a click selects a box; edges snap to other boxes' edges and centres, the frame's, and
  the grid.

The panel on the right names the selected box and fills it: its *kind* and a line of
*content* (a text's lines with ``|`` between them; a file for an image, shot or panel;
a shape's kind; a scene for ``last_frame``), applied with *Apply*. Keys:

=========  ================================================================
Key        Does
=========  ================================================================
``u``      undo
``delete`` remove the selected box (also ``backspace``)
``g``      grid on or off
``t``      the scene's next second (the slider moves too)
=========  ================================================================

Every change is written at once (:class:`~flowreel.editor.layout_state.DesignState`),
so the window can be closed at any time. A change the layout's reader refuses is not
made; the status line says why.
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from flowreel.editor.layout_state import CORNERS, DesignError, DesignState

OUTLINE = "#ffcc33"
SELECTED = "#33ccff"
TEXT = "#e8e8e8"
#: Pixels of the film within which a press grabs a corner of the selected box.
HANDLE = 24.0


class DesignWindow:
    """The window on ``state`` (see the module). ``off_screen`` draws with Agg, for
    tests and pictures."""

    def __init__(self, state: DesignState, off_screen: bool = False, size=(1280, 760)):
        import matplotlib
        if off_screen:
            matplotlib.use("Agg", force=True)
        import matplotlib.pyplot as plt
        from matplotlib.widgets import Button, RadioButtons, Slider, TextBox

        from flowreel.film import model as M
        self.state = state
        self.time = 0.0
        self._drag = None
        self._picture_key = None
        self._picture = None
        self.fig = plt.figure(figsize=(size[0] / 100, size[1] / 100), dpi=100)
        self.fig.patch.set_facecolor("#202020")
        self.ax = self.fig.add_axes((0.02, 0.14, 0.72, 0.8))
        self.ax.set_facecolor("#000000")
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.status = self.fig.text(0.02, 0.965, "", color=TEXT, fontsize=10, va="center")
        self.slider = Slider(self.fig.add_axes((0.08, 0.06, 0.6, 0.03)), "Time", 0.0,
                             max(self._length(), 1e-3), valinit=0.0)
        self.slider.on_changed(self.set_time)
        self.name_box = TextBox(self.fig.add_axes((0.8, 0.86, 0.17, 0.04)), "Name ")
        self.kind = RadioButtons(self.fig.add_axes((0.8, 0.55, 0.17, 0.28)), M.KINDS)
        self.content = TextBox(self.fig.add_axes((0.8, 0.48, 0.17, 0.04)), "Fill ")
        self.apply_button = Button(self.fig.add_axes((0.8, 0.41, 0.17, 0.05)), "Apply")
        self.apply_button.on_clicked(lambda _e: self.apply())
        for w in (self.name_box, self.content):
            w.label.set_color(TEXT)
        self.fig.canvas.mpl_connect("button_press_event", self.on_press)
        self.fig.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.fig.canvas.mpl_connect("button_release_event", self.on_release)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.redraw()

    # -- what is shown -----------------------------------------------------------------

    def _length(self) -> float:
        from flowreel.film.model import load
        from flowreel.film.scene_build import scene_length
        film = load(self.state.film_path)
        try:
            return scene_length(film.scene(self.state.scene), film)
        except ValueError:
            return film.scene(self.state.scene).seconds or 1.0

    def picture(self) -> np.ndarray:
        """The scene at the slider's time, as the build draws it; the boxes without
        their timed contents when those cannot be drawn (a shot not rendered yet)."""
        from flowreel.film.boxes import Contents, draw_frame
        from flowreel.film.model import load
        from flowreel.film.scene_build import SceneBuilder
        key = (repr(self.state.boxes), self.time)
        if key == self._picture_key:
            return self._picture
        film = load(self.state.film_path)
        scene = film.scene(self.state.scene)
        length = self._length()
        try:
            builder = SceneBuilder(film)
            timed = builder._timed(scene)
            try:
                j = min(round(self.time * film.fps), builder.plan.placed(scene.name).frames - 1)
                image = builder.frame(scene.name, j, {}, timed)
            finally:
                for t in timed.values():
                    t.close()
        except (ValueError, KeyError, OSError):
            image = draw_frame(film, scene, self.time, Contents(), length=length)
        self._picture_key, self._picture = key, np.asarray(image)
        return self._picture

    def redraw(self) -> None:
        """Draw the scene, the boxes' outlines and names, and the status line."""
        from matplotlib.patches import Rectangle
        s = self.state
        W, H = s.size
        self.ax.clear()
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        self.ax.imshow(self.picture(), extent=(0, W, H, 0), interpolation="bilinear")
        self.ax.set_xlim(0, W)
        self.ax.set_ylim(H, 0)
        for name in s.names():
            x, y, w, h = s.rect(name)
            colour = SELECTED if name == s.selected else OUTLINE
            self.ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=colour,
                                        linewidth=2 if name == s.selected else 1,
                                        linestyle="-" if name == s.selected else "--"))
            self.ax.text(x + 6, y + 6, name, color=colour, fontsize=9, va="top")
            if name == s.selected:
                for cx, cy in self._corners(name).values():
                    self.ax.add_patch(Rectangle((cx - 8, cy - 8), 16, 16, color=SELECTED))
        if self._drag is not None and self._drag.get("rect") is not None:
            x, y, w, h = self._drag["rect"]
            self.ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=SELECTED,
                                        linestyle=":", linewidth=2))
        grid = f"grid {s.grid:g} px" if s.grid else "no grid"
        self.status.set_text(f"scene {s.scene}  |  {len(s.boxes)} boxes  |  {grid}  |  "
                             f"t = {self.time:.2f} s  |  {s.message}")
        self.fig.canvas.draw_idle()

    def _corners(self, name: str) -> dict:
        x, y, w, h = self.state.rect(name)
        return {"top_left": (x, y), "top_right": (x + w, y),
                "bottom_left": (x, y + h), "bottom_right": (x + w, y + h)}

    # -- acting on the state -----------------------------------------------------------

    def _do(self, action, *args) -> bool:
        """Do ``action``; a refusal goes to the status line. Returns whether it was done."""
        try:
            action(*args)
        except DesignError as exc:
            self.state.message = f"not done: {exc}"
            self.redraw()
            return False
        self._sync()
        self.redraw()
        return True

    def _sync(self) -> None:
        """The panel shows the selected box's name and kind."""
        s = self.state
        if s.selected is None or s.selected not in s.names():
            return
        box = s.layout().boxes[s.index(s.selected)]
        self.name_box.set_val(box.name)
        from flowreel.film.model import KINDS
        self.kind.set_active(KINDS.index(box.kind))

    def select(self, name: str | None) -> None:
        """Select box ``name`` (``None``: none)."""
        self.state.selected = name
        self._sync()
        self.redraw()

    def apply(self) -> bool:
        """Name and fill the selected box from the panel."""
        s = self.state
        if s.selected is None:
            s.message = "select a box first"
            self.redraw()
            return False
        new = self.name_box.text.strip()
        if new and new != s.selected and not self._do(s.rename, s.selected, new):
            return False
        value = self.content.text
        if value.strip():
            return self._do(s.fill, s.selected, self.kind.value_selected, value)
        return True

    def set_time(self, value: float) -> None:
        """Show the scene at ``value`` seconds."""
        self.time = float(value)
        self.redraw()

    # -- events ------------------------------------------------------------------------

    def on_press(self, event) -> None:
        """A press: on the selected box's corner, a resize; on a box, a move; else a new box."""
        if event.inaxes is not self.ax or event.xdata is None:
            return
        s, x, y = self.state, event.xdata, event.ydata
        if s.selected is not None and s.selected in s.names():
            for corner, (cx, cy) in self._corners(s.selected).items():
                if abs(cx - x) <= HANDLE and abs(cy - y) <= HANDLE:
                    self._drag = {"mode": "resize", "corner": corner, "start": (x, y), "rect": None}
                    return
        hit = s.at(x, y)
        if hit is not None:
            self.select(hit)
            self._drag = {"mode": "move", "start": (x, y), "rect": None}
        else:
            self._drag = {"mode": "draw", "start": (x, y), "rect": None}

    def on_motion(self, event) -> None:
        """A drag: the box as it would be, shown dotted."""
        if self._drag is None or event.inaxes is not self.ax or event.xdata is None:
            return
        (x0, y0), x, y = self._drag["start"], event.xdata, event.ydata
        mode = self._drag["mode"]
        if mode == "draw":
            self._drag["rect"] = (min(x0, x), min(y0, y), abs(x - x0), abs(y - y0))
        elif mode == "move":
            bx, by, bw, bh = self.state.rect(self.state.selected)
            self._drag["rect"] = (bx + x - x0, by + y - y0, bw, bh)
        else:
            bx, by, bw, bh = self.state.rect(self.state.selected)
            left, top, right, bottom = bx, by, bx + bw, by + bh
            corner = self._drag["corner"]
            left, right = (x, right) if "left" in corner else (left, x)
            top, bottom = (y, bottom) if "top" in corner else (top, y)
            self._drag["rect"] = (min(left, right), min(top, bottom), abs(right - left),
                                  abs(bottom - top))
        self.redraw()

    def on_release(self, event) -> None:
        """The drag done: the box drawn, moved or resized (or a click: selected)."""
        drag, self._drag = self._drag, None
        if drag is None:
            return
        x = event.xdata if event.inaxes is self.ax and event.xdata is not None else drag["start"][0]
        y = event.ydata if event.inaxes is self.ax and event.ydata is not None else drag["start"][1]
        (x0, y0), s = drag["start"], self.state
        if drag["mode"] == "draw":
            if abs(x - x0) < 4 and abs(y - y0) < 4:          # a click on empty space
                self.select(None)
                return
            self._do(s.add, x0, y0, x, y)
        elif drag["mode"] == "move":
            if abs(x - x0) < 2 and abs(y - y0) < 2:
                self.redraw()
                return
            self._do(s.move, s.selected, x - x0, y - y0)
        else:
            self._do(s.resize, s.selected, drag["corner"], x, y)

    def on_key(self, event) -> None:
        """A key (see the module)."""
        s, key = self.state, event.key
        if key == "u":
            self._do(s.undo)
        elif key in ("delete", "backspace") and s.selected is not None:
            self._do(s.remove, s.selected)
        elif key == "g":
            s.grid = 0.0 if s.grid else 20.0
            s.message = "grid on" if s.grid else "grid off"
            self.redraw()
        elif key == "t":
            length = self.slider.valmax
            self.slider.set_val(0.0 if self.time + 1 > length else self.time + 1)

    def show(self) -> None:
        """Open the window (until it is closed)."""
        import matplotlib.pyplot as plt
        plt.show()


def event(window: DesignWindow, x: float, y: float, key: str | None = None):
    """A mouse or key event at film pixel ``(x, y)`` of ``window``'s scene, as matplotlib
    sends it (for tests and scripts)."""
    return SimpleNamespace(inaxes=window.ax, xdata=x, ydata=y, button=1, key=key)


__all__ = ["DesignWindow", "event", "CORNERS"]
