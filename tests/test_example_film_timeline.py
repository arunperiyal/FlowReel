"""examples/film_timeline/run.py: a short film laid out from its files."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "film_timeline" / "run.py"


def test_example_prints_the_timeline(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == [
        "wake      0.00 s +  5.00 s",
        "compare   5.00 s +  9.00 s",
        "  freeze on frame 16 at 2 s for 3 s",
        "end      14.00 s +  4.00 s",
        "   0.50 to  3.00 s  A smooth cylinder in a steady current",
        "   3.20 to  6.00 s  Each cycle sheds one vortex from each side,",
        "   7.30 to  9.80 s  The grooved cylinder barely moves",
        "  11.00 to 14.00 s  rms $C_L$: 0.55 → 0.06",
        "film 18.00 s"]
