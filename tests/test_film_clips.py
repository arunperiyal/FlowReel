"""Base clips (film/clips.py): lengths, rates, freezes and keys, on generated frames."""
import os

import numpy as np
import pytest

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.clips import Clips, rate_filter

from film_project import colour, decode, film_file, frames, mean_colour, need_ffmpeg


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def clips(folder, shots, **top):
    return Clips(film.load(film_file(folder, shots, **top)))


def test_rate_filters():
    assert rate_filter(24, 24, "interpolate") == "null"
    assert rate_filter(8, 24, "repeat") == "fps=24,tpad=stop_mode=clone:stop=3"
    assert rate_filter(8, 24, "blend").startswith("framerate=fps=24,")
    assert rate_filter(12, 24, "interpolate").startswith("tpad=stop_mode=clone:stop=1,minterpolate=fps=24")


@pytest.mark.parametrize("to_output", ["interpolate", "repeat", "blend"])
def test_a_frames_shot_lasts_its_frames_over_its_rate(tmp_path, to_output):
    frames(tmp_path / "f", 10)
    c = clips(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8, "to_output": to_output}}])
    clip = c.base("a")
    assert clip.frames == 30 and ff.frame_count(clip.path) == 30
    assert ff.length(clip.path) == pytest.approx(10 / 8, abs=0.01)
    pictures = decode(clip.path)
    assert pictures.shape == (30, 90, 160, 3)
    for i in range(10):                                 # flow frames land on their steps
        assert np.abs(mean_colour(pictures[3 * i]) - colour(i)).max() < 6
    assert np.abs(pictures[29].astype(int) - pictures[27]).max() < 4   # the last held


def test_repeat_shows_each_frame_for_a_whole_step(tmp_path):
    frames(tmp_path / "f", 4)
    c = clips(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8, "to_output": "repeat"}}])
    p = decode(c.base("a").path).astype(int)
    for i in range(4):
        for j in (1, 2):
            assert np.abs(p[3 * i + j] - p[3 * i]).max() < 4


def test_a_freeze_holds_its_frame(tmp_path):
    """Frozen at 0.5 s (frame 4 at 8 fps) for 1 s: 24 output frames of frame 4."""
    frames(tmp_path / "f", 10)
    c = clips(tmp_path, [{"name": "a", "frames": "f", "rate": {"fps": 8},
                          "freezes": [{"at": 0.5, "hold": 1.0}]}])
    clip = c.base("a")
    assert clip.frames == 54 and ff.frame_count(clip.path) == 54
    p = decode(clip.path).astype(int)
    held = p[12:12 + 25]           # frame 4, held 24 more; the last step moves on to frame 5
    assert np.abs(held - held[0]).max() < 4
    assert np.abs(mean_colour(held[0]) - colour(4)).max() < 6


def test_frames_of_another_size_are_fitted_on_black(tmp_path):
    frames(tmp_path / "f", 2, size=(80, 80))
    c = clips(tmp_path, [{"name": "a", "frames": "f"}])
    p = decode(c.base("a").path)
    assert p.shape[1:] == (90, 160, 3)
    assert p[0, 45, 5].max() < 20                       # pillarboxed
    assert np.abs(p[0, 45, 80].astype(int) - colour(0)).max() < 8


def test_a_clip_is_kept_until_what_it_shows_changes(tmp_path):
    frames(tmp_path / "f", 6)
    shots = [{"name": "a", "frames": "f", "rate": {"fps": 8}}]
    first = clips(tmp_path, shots).base("a")
    assert first.built
    again = clips(tmp_path, shots).base("a")
    assert not again.built and again.path == first.path
    from PIL import Image
    Image.new("RGB", (160, 90), (0, 0, 0)).save(tmp_path / "f" / "frame_00003.png")
    os.utime(tmp_path / "f" / "frame_00003.png", ns=(1, 1))   # even with an old date
    redrawn = clips(tmp_path, shots).base("a")
    assert redrawn.built and redrawn.key != first.key and not first.path.exists()
    shots[0]["rate"]["to_output"] = "repeat"
    assert clips(tmp_path, shots).base("a").key != redrawn.key
    forced = Clips(film.load(tmp_path / "film.yml"), force=True).base("a")
    assert forced.built


def test_a_missing_frame_is_named(tmp_path):
    frames(tmp_path / "f", 4)
    (tmp_path / "f" / "frame_00002.png").unlink()
    c = clips(tmp_path, [{"name": "a", "frames": "f"}])
    with pytest.raises(FileNotFoundError, match="frame_00002.png is missing"):
        c.base("a")
