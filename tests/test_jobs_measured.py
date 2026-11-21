"""jobs.measured: a render records what a frame costs; rendering.missing finds what is left."""
import pytest

from flowreel.jobs import measured
from flowreel.scene.rendering import missing, render

from test_cli_shot import CAMERAS, SHOT


@pytest.fixture
def shot(tmp_path, monkeypatch):
    (tmp_path / "g.yml").write_text(SHOT)
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    monkeypatch.chdir(tmp_path)
    return tmp_path / "g.yml"


def test_save_load_and_from_frames(tmp_path):
    assert measured.from_frames([0, 0], [1.0, 2.0], 1) is None       # nothing measured
    m = measured.from_frames([100, 300, 200], [1.0, 3.0, 2.0], 2)
    assert (m.peak_bytes, m.seconds, m.threads, m.frames) == (300, 2.0, 2, 3)
    assert measured.load(tmp_path) is None
    measured.save(tmp_path, m)
    assert measured.load(tmp_path) == m
    (tmp_path / measured.FILE).write_text("{broken")
    assert measured.load(tmp_path) is None


def test_a_render_records_its_frames_and_missing_finds_the_rest(shot, tmp_path):
    out = tmp_path / "frames"
    try:
        render(shot, [0, 1, 2], out=out, jobs=2, check_memory=False)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    m = measured.load(out / "g")
    assert m is not None and m.frames == 3 and m.peak_bytes > 50 * 1024 ** 2 and m.seconds > 0
    assert missing(shot, out=out) == [3, 4, 5]
    assert missing(shot, [1, 4], out=out) == [4]
    (out / "g" / "frame_00001.png").unlink()
    assert missing(shot, out=out) == [1, 3, 4, 5]
    assert missing(shot, out=out, scale=0.5) == [0, 1, 2, 3, 4, 5]     # a draft has its own
