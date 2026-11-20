"""ffmpeg (film/ffmpeg.py): found in order, checked once, errors that name the binary."""
import os
import stat
import sys
from pathlib import Path

import pytest

from flowreel.film import ffmpeg as ff
from flowreel.film.ffmpeg import FfmpegError, check, parse_version

GOOD = """#!/bin/sh
case "$*" in
  *-version*) echo "ffmpeg version {version} Copyright (c) 2000-2025";;
  *-filters*) printf ' ... minterpolate      V->V  x\\n ... xfade  VV->V x\\n ... fade V->V x\\n ... overlay VV->V x\\n ... tpad V->V x\\n ... framerate V->V x\\n ... scale V->V x\\n';;
  *-encoders*) printf ' V....D {encoder}  H.264\\n A....D aac  AAC\\n';;
esac
"""


def fake(folder: Path, version="8.0.1", encoder="libx264", probe=True) -> Path:
    path = folder / "ffmpeg"
    path.write_text(GOOD.format(version=version, encoder=encoder))
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    if probe:
        (folder / "ffprobe").write_text("#!/bin/sh\n")
    return path


@pytest.mark.parametrize("line, version", [
    ("ffmpeg version 8.0.1 Copyright", (8, 0, 1)),
    ("ffmpeg version 4.3.1 Copyright", (4, 3, 1)),
    ("ffmpeg version n7.1-3-gdeadbeef Copyright", (7, 1)),
    ("ffmpeg version 6.1.1-3ubuntu5 Copyright", (6, 1, 1)),
    ("ffmpeg version N-112233-gabc Copyright", None),
])
def test_versions_are_read(line, version):
    assert parse_version(line) == version


def test_a_good_build_passes(tmp_path):
    found = check(fake(tmp_path), "the path")
    assert found.version == (8, 0, 1) and found.ffprobe == tmp_path / "ffprobe"


def test_an_old_build_is_named_with_where_it_came_from(tmp_path):
    with pytest.raises(FfmpegError, match=r"ffmpeg \(from the path\) is ffmpeg 4\.3\.1.*5\.1 "
                                          r"or later.*conda-forge"):
        check(fake(tmp_path, version="4.3.1"), "the path")


def test_a_missing_encoder_or_ffprobe_is_an_error(tmp_path):
    with pytest.raises(FfmpegError, match="lacks encoder libx264"):
        check(fake(tmp_path, encoder="mpeg4"))
    (tmp_path / "ffprobe").unlink()
    with pytest.raises(FfmpegError, match="no ffprobe beside"):
        check(fake(tmp_path, probe=False))


def test_ffmpeg_is_looked_for_in_order(tmp_path, monkeypatch):
    named = fake(tmp_path)
    monkeypatch.setenv("FFMPEG", str(named))
    found = ff.candidates()
    assert found[0] == ("FFMPEG", named)
    beside = Path(sys.executable).parent / "ffmpeg"
    if beside.is_file():
        assert ("the Python environment", beside) in found
    monkeypatch.delenv("FFMPEG")
    assert all(how != "FFMPEG" for how, _ in ff.candidates())


def test_the_environments_ffmpeg_passes_the_check():
    """The real one: conda-forge's, beside this Python, or the one on the path."""
    if not ff.candidates():
        pytest.skip("no ffmpeg installed")
    found = ff.find()
    assert found.version[:2] >= ff.MIN_VERSION and found.ffprobe.is_file()
