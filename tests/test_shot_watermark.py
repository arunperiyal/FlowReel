"""A shot's watermark: drawn into its frames after the screenshot, scaled in drafts, and
part of each frame's key, so changing it draws the frames again."""
import numpy as np

from flowreel.scene.keys import frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.template import HEADER

from test_render import VIEWS, picture, toy_shot

MARK = {"text": "AP", "corner": "upper_left", "size": 12, "colour": "#00ff00", "opacity": 1}


def green(frame):
    return (frame[..., 1] > 200) & (frame[..., 0] < 80) & (frame[..., 2] < 80)


def test_the_watermark_is_drawn_into_the_frame(toy_source):
    plain = picture(toy_shot(), toy_source)
    marked = picture(toy_shot(watermark=MARK), toy_source)
    assert not green(plain).any()
    ys, xs = np.nonzero(green(marked))
    assert xs.max() < 32 and ys.max() < 24                    # in the upper left corner
    assert (marked[24:, 32:] == plain[24:, 32:]).all()        # and nowhere else


def test_a_draft_scales_it_with_the_picture(toy_source):
    full = green(picture(toy_shot(watermark=MARK, size=[128, 96]), toy_source))
    half = green(picture(toy_shot(watermark=MARK, size=[128, 96]), toy_source, scale=0.5))
    assert 0.15 < half.sum() / full.sum() < 0.4               # about a quarter of the area


def test_it_is_part_of_the_frame_key(toy_source):
    def key(**extra):
        return frame_key(Scene.make(toy_shot(**extra), toy_source, VIEWS), 0)
    plain = key()
    assert key(watermark=MARK) != plain
    assert key(watermark={**MARK, "opacity": 0.5}) != key(watermark=MARK)
    assert key(watermark=MARK) == key(watermark=dict(MARK))


def test_the_shot_template_mentions_it():
    assert "# watermark:" in HEADER
