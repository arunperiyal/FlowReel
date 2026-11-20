"""Finished clips: fades on the picture, then captions, shapes and the watermark on top,
with their own times and fades; keys that rebuild only what changed."""
import numpy as np
import pytest
from PIL import Image

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.clips import Clips

from film_project import decode, film_file, need_ffmpeg

RED = {"lines": ["X"], "place": "centre", "size": 60, "colour": "#ff0000", "shadow": False,
       "fade": 0.25}


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def grey(folder, n, level=120):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", (160, 90), (level,) * 3).save(folder / f"frame_{i:05d}.png")


def red(frame) -> float:
    """Share of pixels clearly red: the caption's ink."""
    f = frame.astype(int)
    return ((f[..., 0] > 180) & (f[..., 1] < 90) & (f[..., 2] < 90)).mean()


def make(tmp_path, shots, **top):
    return Clips(film.load(film_file(tmp_path, shots, **top)))


def test_a_caption_shows_between_its_times_with_its_fades(tmp_path):
    grey(tmp_path / "f", 36)
    c = make(tmp_path, [{"name": "a", "frames": "f", "text": [{**RED, "at": [0.5, 1.0]}]}])
    clip = c.finished("a")
    assert ff.frame_count(clip.path) == 36 and clip.frames == 36
    p = decode(clip.path).astype(int)
    strength = [int((f[..., 0] - f[..., 1]).max()) for f in p]   # red over the grey
    assert strength[12] == 0 and strength[24] == 0             # t = 0.5 and 1.0: not yet, gone
    assert strength[18] > 240                                  # t = 0.75: full
    assert strength[12] < strength[14] < strength[16] < strength[18]   # 0.25 s fade in
    assert strength[18] > strength[20] > strength[22] > strength[24]   # and out
    assert max(strength[:12]) == 0 and max(strength[25:]) == 0


def test_fades_act_on_the_picture_under_the_text(tmp_path):
    """Faded out from 0.5 s: the picture goes black, the caption stays."""
    grey(tmp_path / "f", 36)
    c = make(tmp_path, [{"name": "a", "frames": "f", "fade": [0.25, 0.5], "fade_out_at": 0.5,
                         "text": [{**RED, "at": [0.0, 1.5]}]}])
    p = decode(c.finished("a").path).astype(int)
    assert p[0, 5, 5].max() < 20                          # faded in from black
    assert abs(p[12, 5, 5].mean() - 120) < 8              # the picture, at 0.5 s
    assert p[30, 5, 5].max() < 20                         # black after the fade out
    assert red(p[30]) > 0.01                              # with the caption on it


def test_a_caption_runs_across_a_cut(tmp_path):
    grey(tmp_path / "f", 24)
    grey(tmp_path / "g", 24, level=60)
    c = make(tmp_path, [
        {"name": "a", "frames": "f", "text": [{**RED, "at": [0.5, {"shot": "b", "at": 0.5}]}]},
        {"name": "b", "frames": "g"}])
    (cap, start, end, fade_in, fade_out), = c.captions("b")
    assert (start, end, fade_in, fade_out) == (0, 0.5, False, True)
    a, b = decode(c.finished("a").path), decode(c.finished("b").path)
    assert red(a[23]) > 0.01 and red(b[0]) > 0.01        # no fade at the cut
    assert red(b[20]) == 0


def test_the_watermark_shows_on_the_shots_it_names(tmp_path):
    grey(tmp_path / "f", 12, level=20)
    grey(tmp_path / "g", 12, level=20)
    c = make(tmp_path, [{"name": "a", "frames": "f"}, {"name": "b", "frames": "g"}],
             watermark={"text": "WM", "size": 30, "opacity": 1, "colour": "#00ff00",
                        "shots": ["b"]})
    green = lambda f: ((f[..., 1].astype(int) > 180) & (f[..., 0] < 100)).mean()
    assert green(decode(c.finished("a").path)[6]) == 0
    assert green(decode(c.finished("b").path)[6]) > 0.005


def test_a_caption_change_rebuilds_the_finished_clip_only(tmp_path):
    grey(tmp_path / "f", 12)
    shots = [{"name": "a", "frames": "f", "text": [{**RED, "at": [0.1, 0.4]}]}]
    c = make(tmp_path, shots)
    base, done = c.base("a"), c.finished("a")
    again = make(tmp_path, shots)
    assert not again.finished("a").built and not again.base("a").built
    shots[0]["text"][0]["lines"] = ["Y"]
    changed = make(tmp_path, shots)
    redone = changed.finished("a")
    assert redone.built and redone.key != done.key and not changed.base("a").built
    assert not done.path.exists() and changed.base("a").path == base.path
    assert (tmp_path / "clips" / "caption_a_0.png").is_file()
