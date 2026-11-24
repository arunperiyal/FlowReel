"""Draw frames 0, 12 and 23 of shots/flow_layers.yml from a generated solid-body vortex.

Usage: python run.py [DIR]   (default ./flow_layers_example)

Needs no data: vortex_case.py (examples/) writes a small VTK flow, u = (-y, x, 0) on a
17 x 17 x 9 grid, and a sphere into DIR/vtk/, and imports them as the tag ``vortex``
(``data import vtk``). The shot names that tag. Pictures go to DIR/flow_layers_<frame>.png.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import vortex_case  # noqa: E402

from flowreel.scene import render_frame  # noqa: E402
from flowreel.scene.shot import load  # noqa: E402

HERE = Path(__file__).parent


def main(folder: Path) -> list[Path]:
    """Make the project in ``folder``, draw three frames, return their files."""
    folder.mkdir(parents=True, exist_ok=True)
    vortex_case.make_project(folder)
    (folder / "shots").mkdir(exist_ok=True)
    shutil.copy(HERE / "shots" / "flow_layers.yml", folder / "shots" / "flow_layers.yml")
    shutil.copy(HERE / "cameras.yml", folder / "cameras.yml")
    shot = load(folder / "shots" / "flow_layers.yml")
    files = []
    for frame in (0, 12, 23):
        files.append(folder / f"flow_layers_{frame}.png")
        Image.fromarray(render_frame(shot, frame)).save(files[-1])
    return files


if __name__ == "__main__":
    for file in main(Path(sys.argv[1] if len(sys.argv) > 1 else "flow_layers_example")):
        print(file)
