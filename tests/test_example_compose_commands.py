"""examples/compose_commands/run.sh: compose panel and compose layout on generated data."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RUN = Path(__file__).parent.parent / "examples" / "compose_commands" / "run.sh"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_example_runs_the_compose_commands(tmp_path):
    env = {**os.environ, "FLOWREEL": f"{sys.executable} -m flowreel"}
    done = subprocess.run(["sh", str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600, env=env, cwd=tmp_path)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = [l for l in done.stdout.splitlines() if not l.startswith("  ")]
    assert lines[0].startswith("16 drawn, 0 skipped")
    assert lines[1].startswith("16 composed, 0 skipped")
    assert lines[2].startswith("4 composed") and "rate_board@480x360" in lines[2]
    assert (tmp_path / "ex" / "frames" / "phase" / "frame_00015.png").exists()
