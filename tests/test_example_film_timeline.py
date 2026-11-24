"""examples/film_timeline/run.py: a short film of scenes planned from its files."""
import subprocess
import sys
from pathlib import Path

RUN = Path(__file__).parent.parent / "examples" / "film_timeline" / "run.py"


def test_example_prints_the_plan_and_the_captions(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    lines = done.stdout.splitlines()
    assert [line.split()[:2] for line in lines[1:5]] == [
        ["wake", "5.00"], ["compare", "9.00"], ["end", "4.00"], ["film", "18.00"]]
    times = [line for line in lines if "-->" in line]
    assert times == ["00:00:00,500 --> 00:00:03,000", "00:00:03,200 --> 00:00:04,900",
                     "00:00:05,300 --> 00:00:06,800", "00:00:07,000 --> 00:00:10,000"]
    assert "The grooved cylinder barely moves" in lines
