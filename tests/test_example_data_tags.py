"""examples/data_tags/run.py runs from a clean folder: two tags, both with a body cyl."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "data_tags" / "run.py"


def test_example_imports_checks_renames_and_removes(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout
    assert "grooved: ok, 2 steps" in out and "smooth: ok, 4 steps" in out
    assert "body cyl: zone cyl" in out
    assert "renamed data/grooved/ to data/helical/" in out
    assert "the case itself is untouched" in out
    assert list((tmp_path / "ex" / "cases" / "grooved" / "case").glob("*.plt"))
    assert not (tmp_path / "ex" / "film" / "data" / "helical").exists()
