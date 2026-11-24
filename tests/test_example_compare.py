"""examples/compare/run.py: the comparison and lift map of two generated cases, as scenes."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "compare" / "run.py"


def test_example_plans_and_previews_the_comparison_and_the_lift_map(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    # 24 wake frames at 4 a second (6 s) and a freeze of a second; 33 map times at 4 a second
    rows = {line.split()[0]: line.split()[1] for line in lines if line.split()[:1] in
            (["compare"], ["liftmap"], ["film"])}
    assert rows == {"compare": "7.00", "liftmap": "8.25", "film": "15.25"}
    assert lines[-2:] == ["3 stills of compare -> frames/scenes/compare",
                          "2 stills of liftmap -> frames/scenes/liftmap"]
    assert (tmp_path / "ex" / "frames" / "scenes" / "compare" / "at_5.00.png").is_file()
