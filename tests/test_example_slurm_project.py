"""examples/slurm_project/run.py: a generated shot rendered through a fake sbatch."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "slurm_project" / "run.py"


def test_example_measures_renders_and_resumes(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout
    assert "measuring job" in out and "-> 24 frames drawn" in out
    assert "24 frames in 2 tasks of up to 16 frames   (only task 0 runs)" in out
    assert "-> 16 frames left" in out and "8 frames in 1 task" in out
    assert out.count("-> 24 frames drawn") == 2
    assert "1004  wake (render)" in out
