"""The watermark (film/watermark.py): drawn in a corner or a place, at its opacity; when
it shows in the film; and drawn into a shot's frames, part of their key."""
import numpy as np
import pytest
from PIL import Image

from flowreel.film import model as M
from flowreel.film.scene_build import _watermark_on
from flowreel.film.schema import parse_watermark
from flowreel.film.watermark import key_fields, stamp, watermark_image
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
    scenes = [{"name": name, "seconds": 2, "layout": {"boxes": [{"text": name}]}}
              for name in ("a", "b")]
    return M.from_dict({"scenes": scenes, "watermark": watermark},
                       file=str(tmp_path / "film.yml"))


def shown(film, at):
    """Whether the watermark shows at film second ``at`` (scenes of 2 s)."""
    scene = film.scenes[int(at // 2)]
    return _watermark_on(film.watermark, scene, int(at // 2) * 2.0, at % 2)


def test_by_default_it_shows_over_every_scene(tmp_path):
    f = film(tmp_path, text="w")
    assert [shown(f, t) for t in (0.5, 2.5)] == [True, True]


def test_scenes_or_seconds_say_when(tmp_path):
    f = film(tmp_path, text="w", scenes=["b"])
    assert [shown(f, t) for t in (0.5, 2.5)] == [False, True]
    f = film(tmp_path, text="w", seconds=[1, 3])
    assert [shown(f, t) for t in (0.5, 1.5, 2.5, 3.5)] == [False, True, True, False]
    assert _watermark_on(None, f.scenes[0], 0.0, 0.0) is False
