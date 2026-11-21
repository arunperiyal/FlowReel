"""examples/slurm_script/run.py: a job array script written, and a job refused."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "slurm_script" / "run.py"


def test_example_writes_the_script(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [
        "wrote render.sh for partition part1",
        "refused: partition part1 of airavata runs a job for at most 03:00:00; asked 05:00:00"]
    text = (tmp_path / "ex" / "render.sh").read_text()
    assert "#SBATCH --array=0-3%2" in text and "--frames 90:120 -j 4 ;;" in text
    assert (tmp_path / "ex" / "logs").is_dir()
    assert subprocess.run(["bash", "-n", str(tmp_path / "ex" / "render.sh")]).returncode == 0
