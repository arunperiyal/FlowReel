"""examples/flow_panels/run.py: a section, cuts and a strip of the generated cylinder."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "flow_panels" / "run.py"


def test_example_draws_the_flow_panels(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == ["section: 4 drawn", "cuts: 4 drawn", "strip: 4 drawn",
                                        "board: 4 composed"]
