"""examples/film_build/run.py: a small film of scenes built from generated frames and a tone."""
import subprocess
import sys
from pathlib import Path

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "film_build" / "run.py"
REPORT = [
    "scene    planned  measured",
    "opening    2.00 s    2.00 s  {}",
    "wake       4.50 s    4.50 s  {}",
    "end        2.00 s    2.00 s  {}",
    "film       8.50 s    8.50 s  film.mp4",
    "preview film_180p.mp4",
    "srt film.srt",
    "chapters chapters.txt",
    "chapters shorter than YouTube's 10 s: Opening, The wake, Thanks",
    "audio tone.wav: 0.00 to 8.50 s of the film (file 20.00 s)",
    "wrote contact.png"]


def run(out):
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True, text=True,
                          timeout=600)
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout.splitlines()


def test_example_builds_the_film_then_keeps_its_clips(tmp_path):
    need_ffmpeg()
    assert run(tmp_path / "ex") == [line.format("built") for line in REPORT]
    assert run(tmp_path / "ex") == [line.format("kept") for line in REPORT]
    assert (tmp_path / "ex" / "chapters.txt").read_text() == \
        "0:00 Opening\n0:02 The wake\n0:07 Thanks\n"
