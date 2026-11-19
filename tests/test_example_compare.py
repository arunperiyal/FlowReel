"""examples/compare/run.py: the comparison and lift map of two generated cases."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "compare" / "run.py"


def test_example_composes_the_comparison_and_the_lift_map(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    # 23 wake frames played at three times their rate: 70 output frames, and a freeze of 24
    assert done.stdout.splitlines() == ["compare: 24 composed", "liftmap: 33 drawn",
                                        "compare_flow: 24 composed, 0 skipped",
                                        "plots_output: 94 drawn at (1280, 0)"]
