"""examples/panels/run.py: series and phase panels of a history-only tag, drawn, skipped, and
tiled in a scene with a freeze."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "panels" / "run.py"


def test_example_draws_panels(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert lines[:4] == ["16 drawn, 0 skipped -> frames/compare",
                         "16 drawn, 0 skipped -> frames/phase",
                         "0 drawn, 16 skipped -> frames/compare",
                         "0 drawn, 16 skipped -> frames/phase"]
    # 16 times at 2 a second (8 s) plus the freeze's second
    assert any(line.split()[:3] == ["board", "9.00", "s"] for line in lines)
    assert lines[-1] == "3 stills of board -> frames/scenes/board"
    assert len(list((tmp_path / "ex" / "frames" / "scenes" / "board").glob("at_*.png"))) == 3
