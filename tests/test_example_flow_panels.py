"""examples/flow_panels/run.py: a section, cuts and a strip of the generated cylinder, tiled."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "flow_panels" / "run.py"


def test_example_draws_the_flow_panels(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == [
        "4 drawn, 0 skipped -> frames/section", "4 drawn, 0 skipped -> frames/cuts",
        "4 drawn, 0 skipped -> frames/strip", "1 stills of board -> frames/scenes/board"]
    ex = tmp_path / "ex"
    assert (ex / "data" / "cylinder" / "domain.yml").is_file()
    assert (ex / "frames" / "scenes" / "board" / "at_0.50.png").is_file()
