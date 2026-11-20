"""The watermark (film/watermark.py): drawn in a corner or a place, at its opacity; when
it shows in the film; and drawn into a shot's frames, part of their key."""
import numpy as np
import pytest
from PIL import Image

from flowreel.film import from_dict, timeline
from flowreel.film.schema import parse_watermark
from flowreel.film.watermark import key_fields, spans, stamp, watermark_image
from flowreel.scene.errors import Checker, ConfigError

PICTURE = (400, 200)


def mark(tmp_path=None, **spec):
    return parse_watermark(spec, Checker("film.yml", ("watermark",)), tmp_path or ".")


def ink(layer):
    ys, xs = np.nonzero(np.asarray(layer)[..., 3])
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


@pytest.fixture
def logo(tmp_path):
    """A 40 x 20 opaque red logo."""
    path = tmp_path / "logo.png"
    Image.new("RGBA", (40, 20), (255, 0, 0, 255)).save(path)
    return path


@pytest.mark.parametrize("corner", ["upper_left", "upper_right", "lower_left", "lower_right"])
def test_text_sits_in_its_corner_a_margin_from_the_edges(corner):
    left, top, right, bottom = ink(watermark_image(mark(text="A. P.", corner=corner), PICTURE))
    pad = round(0.02 * 200)
    assert abs((left if corner.endswith("left") else 400 - right) - pad) <= 2
    assert abs((top if corner.startswith("upper") else 200 - bottom) - pad) <= 2
    assert 18 <= bottom - top <= 32                          # size 32: a font's capitals and dots


def test_an_image_is_scaled_to_its_size_and_placed(tmp_path, logo):
    w = mark(tmp_path, image="logo.png", size=40, place=[100, 50], opacity=0.5)
    layer = np.asarray(watermark_image(w, PICTURE))
    assert ink(layer) == (100, 50, 180, 90)                  # 40 high, 80 wide
    assert tuple(layer[70, 140]) == (255, 0, 0, 128)
    half = np.asarray(watermark_image(w, PICTURE, scale=0.5))
    assert ink(half) == (50, 25, 90, 45)                     # a draft: scaled with the picture


def test_a_missing_image_or_shot_keys_at_shot_level_are_errors(tmp_path):
    with pytest.raises(ConfigError, match="no image file"):
        mark(tmp_path, image="nowhere.png")
    with pytest.raises(ConfigError, match="unknown key 'seconds'"):
        parse_watermark({"text": "w", "seconds": [0, 1]}, Checker("s.yml"), tmp_path, shot=True)


def test_stamp_draws_into_a_frame():
    frame = np.zeros((200, 400, 3), np.uint8)
    out = stamp(frame, mark(text="A. P.", colour="#ffffff", opacity=1), 1.0)
    assert out.shape == frame.shape and out.dtype == np.uint8
    left, top, right, bottom = ink(np.dstack([out, out[..., :1]]))
    assert right > 350 and bottom > 170                      # lower right by default
    assert out.max() == 255 and not frame.any()


def test_the_key_follows_the_look_and_the_image_file(tmp_path, logo):
    w = mark(tmp_path, image="logo.png")
    key = key_fields(w)
    assert key_fields(mark(tmp_path, image="logo.png")) == key
    assert key_fields(mark(tmp_path, image="logo.png", opacity=0.3)) != key
    Image.new("RGBA", (40, 30), (0, 255, 0, 255)).save(logo)
    assert key_fields(w) != key
    assert key_fields(None) is None


def film(tmp_path, **watermark):
    card = tmp_path / "card.yml"
    card.write_text("{}\n")
    for name in ("a", "b"):
        (tmp_path / name).mkdir(exist_ok=True)
        for i in range(48):
            (tmp_path / name / f"frame_{i:05d}.png").touch()
    f = from_dict({"shots": [{"name": "card", "card": "card.yml", "seconds": 3},
                             {"name": "a", "frames": "a"}, {"name": "b", "frames": "b"}],
                   "watermark": watermark}, file=str(tmp_path / "film.yml"))
    return f.watermark, timeline(f)


def test_by_default_it_shows_over_every_shot_but_cards(tmp_path):
    w, tl = film(tmp_path, text="w")
    assert spans(w, tl) == [("a", 0, 2), ("b", 0, 2)]
    w, tl = film(tmp_path, text="w", cards=True)
    assert spans(w, tl)[0] == ("card", 0, 3)


def test_shots_or_seconds_say_when(tmp_path):
    w, tl = film(tmp_path, text="w", shots=["b"])
    assert spans(w, tl) == [("b", 0, 2)]
    w, tl = film(tmp_path, text="w", seconds=[4, 6])          # card 0-3, a 3-5, b 5-7
    assert spans(w, tl) == [("a", 1, 2), ("b", 0, 1)]
    assert spans(None, tl) == []
