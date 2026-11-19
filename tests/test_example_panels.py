"""examples/panels/run.py: series and phase panels drawn, tiled, skipped, then tiled by
the layout with the phase panel at the output rate."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "panels" / "run.py"


def test_example_draws_panels(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == ["compare: 16 drawn", "phase: 16 drawn",
                                        "board: 16 composed", "compare: 16 skipped",
                                        "phase: 16 skipped", "rate_board_flow: 16 composed",
                                        "phase_output: 52 drawn at (480, 180)"]
