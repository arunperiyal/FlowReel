"""Render shots/render_shot.yml to DIR/frames, then a half-size draft, then measure one frame.

Usage: python run.py [DIR]   (default ./render_shot_example)

Needs no data: vortex_case.py (examples/) writes a flow, the solid-body vortex
u = (-y, x, 0), and a sphere as VTK files and imports them as the tag ``vortex``. Frames go
to DIR/frames/render_shot/ and DIR/frames/render_shot@320x180/. Run it twice: the second
run skips every frame, because no frame's key changed.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import vortex_case  # noqa: E402

from flowreel.scene import render  # noqa: E402
from flowreel.scene.memory import measure  # noqa: E402

HERE = Path(__file__).parent


def report(r, folder):
    print(f"{r.folder.relative_to(folder)}: {r.count('rendered')} drawn, "
          f"{r.count('skipped')} skipped (backend {r.backend})")


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    vortex_case.make_project(folder)
    (folder / "shots").mkdir(exist_ok=True)
    shot = folder / "shots" / "render_shot.yml"
    shutil.copy(HERE / "shots" / "render_shot.yml", shot)
    shutil.copy(HERE / "cameras.yml", folder / "cameras.yml")
    report(render(shot, out=folder / "frames", jobs=2), folder)
    report(render(shot, out=folder / "frames", jobs=2, scale=0.5), folder)
    print(measure(shot).text())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("render_shot_example"))
