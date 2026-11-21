"""A camera editor session, scripted: what you would do in the window, done in code.

Usage: python run.py [DIR]          (default ./camera_editor_example)
       python run.py [DIR] --window  (opens the window to pick views yourself)

Needs no data, only off-screen rendering. It copies shot.yml and cameras.yml to DIR,
opens the editor on the shot without showing it, and picks the track 'approach': a view
at frame 0, the next time step, a closer view at frame 47, a view replaced, one undone,
and the track played. Every key press writes DIR/cameras.yml at once. It saves a picture
of the window as DIR/editor.png and prints the track, then renders three frames of the
shot on the picked track (DIR/frames/editor_demo@320x180/), as Phase 6's check does.
Last it saves the shot's surfaces to DIR/vtp/ and opens the editor on them, as on a
laptop away from the data.
"""
import shutil
import sys
from pathlib import Path

import pyvista as pv

from flowreel.box import Box
from flowreel.editor.scenes import ShotScenes
from flowreel.editor.state import EditorState
from flowreel.editor.surfaces import SavedScenes, save_shot_surfaces
from flowreel.editor.window import EditorWindow
from flowreel.scene.camera_path import load_tracks
from flowreel.scene import render
from flowreel.scene.rendering import Scene
from flowreel.scene.views import View, load_views

HERE = Path(__file__).parent


class Vortex:
    """Three steps of a solid-body vortex round a sphere, spinning faster each step."""

    name = "vortex"

    def steps(self):
        return [0, 1, 2]

    def time(self, step):
        return float(step)

    def fields(self):
        return ["U", "V", "W"]

    def flow(self, step, fields, crop):
        grid = pv.ImageData(dimensions=(17, 17, 9), spacing=(0.125, 0.125, 0.125),
                            origin=(-1, -1, 0)).cast_to_unstructured_grid()
        x, y = grid.points[:, 0], grid.points[:, 1]
        spin = 1.0 + 0.5 * step
        for name, value in {"U": -spin * y, "V": spin * x, "W": 0 * x}.items():
            grid.point_data[name] = value
        return grid

    def bodies(self):
        return ["sphere"]

    def body(self, step, name=None):
        return pv.Sphere(radius=0.2, center=(0, 0, 0.5))

    def bounds(self):
        return Box((-1, -1, 0), (1, 1, 1))

    def memory_per_step(self, crop):
        return 17 * 17 * 9 * 8 * 8 / 1024 ** 3


def scripted(window: EditorWindow) -> None:
    """What a person would do in the window."""
    window.press("s")                                       # the start view at frame 0
    window.press("n")                                       # look at the next step
    window.set_frame(47)
    window.look(View((1.2, -1.6, 1.4), (0, 0, 0.5), (0, 0, 1), 30))
    window.press("s")                                       # closer, at frame 47
    window.set_frame(30)
    window.look(View((2.4, -0.6, 2.0), (0, 0, 0.5), (0, 0, 1), 30))
    window.press("s")                                       # a key at frame 30 ...
    window.press("u")                                       # ... taken back
    window.set_frame(40)
    window.look(View((1.0, -1.7, 1.2), (0, 0, 0.5), (0, 0, 1), 30))
    window.press("r")                                       # frame 47's view, nudged
    window.press("p")


def main(folder: Path, show: bool = False) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("shot.yml", "cameras.yml"):
        shutil.copy(HERE / name, folder / name)
    scenes = ShotScenes(Scene.make(folder / "shot.yml", source=Vortex()))
    state = EditorState.open(folder / "cameras.yml", "approach", frames=48, steps=scenes.steps)
    window = EditorWindow(state, scenes, size=(960, 540), off_screen=not show,
                          anchors=[("sphere", (0, 0, 0.5))])
    if show:
        window.show()
        return
    scripted(window)
    print(window.message)
    window.plotter.screenshot(folder / "editor.png")
    window.plotter.close()
    views = load_views(folder / "cameras.yml")
    track = load_tracks(folder / "cameras.yml", views)["approach"]
    for frame, view in track.keys:
        print(f"key at frame {frame}: {view.name} from "
              f"({', '.join(f'{x:.1f}' for x in view.position)})")

    picked = folder / "picked.yml"                   # the shot on the picked track
    picked.write_text((folder / "shot.yml").read_text()
                      .replace("camera: {view: start}", "camera: {track: approach}"))
    # In worker processes, as shot render does: the windows above were made with VTK's
    # default OpenGL, and render chooses an off-screen one; one process must not mix them.
    report = render(picked, [0, 24, 47], source=Vortex(), out=folder / "frames", scale=0.5,
                    jobs=2)
    print(f"rendered frames 0, 24 and 47 of the picked track: "
          f"{report.count('rendered')} drawn -> {report.folder.relative_to(folder)}")

    saved = save_shot_surfaces(folder / "shot.yml", folder / "vtp", source=Vortex())
    away = EditorWindow(EditorState.open(folder / "cameras.yml", "approach", 48, saved),
                        SavedScenes(folder / "vtp"), size=(960, 540), off_screen=True)
    away.press("n")
    print(f"saved surfaces of steps {saved}; opened without the data: {away.message}")
    away.plotter.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--window"]
    main(Path(args[0]) if args else Path("camera_editor_example"), "--window" in sys.argv)
