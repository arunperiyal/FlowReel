"""examples/film_commands/run.sh: the film commands on generated frames and a tone."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "film_commands" / "run.sh"


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_example_runs_the_film_commands(tmp_path):
    need_ffmpeg()
    env = {**os.environ, "FLOWREEL": f"{sys.executable} -m flowreel", "PYTHON": sys.executable}
    done = subprocess.run(["sh", str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=600, env=env, cwd=tmp_path)
    assert done.returncode == 0, done.stderr[-2000:]
    out = done.stdout.splitlines()
    assert out[0] == "wrote template.yml"
    first, second = [k for k, l in enumerate(out) if l.startswith("shot ")][::2]
    assert out[first + 2] == "wake       4.50 s       -  "         # lengths, before the build
    assert "-: no finished clip yet (film build)" in out
    assert "wake       4.50 s    4.50 s  built" in out
    assert out[second + 2] == "wake       4.50 s    4.50 s"           # lengths, after it
    assert "Thanks       0:07     7.00 s    1.50 s" in out
    assert any(l.startswith("wrote contact.png") for l in out)
    assert "wrote film.srt: 4 captions" in out
    assert out[-3:] == ["0:00 Opening", "0:02 The wake", "0:07 Thanks"]
    assert "YouTube's 10 s" in done.stderr
    ex = tmp_path / "ex"
    for name in ("film.mp4", "film_180p.mp4", "contact.png", "film.srt", "chapters.txt"):
        assert (ex / name).is_file(), name
