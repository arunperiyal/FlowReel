"""examples/riser500/panels.py: a span map and a locator of the generated riser case."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "riser500" / "panels.py"


def test_example_draws_the_span_panels(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == ["8 drawn, 0 skipped -> frames/span_map",
                                        "8 drawn, 0 skipped -> frames/locator",
                                        "1 stills of board -> frames/scenes/board"]
