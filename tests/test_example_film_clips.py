"""examples/film_clips/run.py: a small film's clips built from generated frames."""
import subprocess
import sys
from pathlib import Path

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "film_clips" / "run.py"


def run(out):
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True, text=True,
                          timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout.splitlines()


def test_example_builds_every_clip_then_keeps_them(tmp_path):
    need_ffmpeg()
    first = run(tmp_path / "ex")
    assert first == [
        "opening   2.00 s   48 frames planned,  48 measured, built",
        "wake      4.50 s  108 frames planned, 108 measured, built",
        "end       2.00 s   48 frames planned,  48 measured, built"]
    assert [line.replace("kept", "built") for line in run(tmp_path / "ex")] == first
    assert all(line.endswith("kept") for line in run(tmp_path / "ex"))
