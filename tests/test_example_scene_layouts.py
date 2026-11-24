"""examples/scene_layouts/run.py: frame folders in boxes, side by side and on a grid."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "scene_layouts" / "run.py"


def test_example_plans_and_previews_the_layouts(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    rows = {line.split()[0]: line.split()[1] for line in lines if line.split()[:1] in
            (["compare"], ["grid"], ["film"])}
    assert rows == {"compare": "1.00", "grid": "1.00", "film": "2.00"}   # 8 frames at 8 a second
    assert lines[-2:] == ["1 stills of compare -> frames/scenes/compare",
                          "1 stills of grid -> frames/scenes/grid"]
    still = tmp_path / "ex" / "frames" / "scenes" / "grid" / "at_0.50.png"
    from PIL import Image
    assert Image.open(still).size == (960, 540)
