"""Draft size: the same shot with fewer pixels, in its own folder."""
import numpy as np
import pytest
from PIL import Image

from flowreel.scene import render
from flowreel.scene.rendering import Scene, draft_size, frame_folder

from test_render import VIEWS, toy_shot


def test_draft_size_is_even_and_exclusive():
    assert draft_size((1920, 1080)) == (1920, 1080)
    assert draft_size((1920, 1080), scale=0.5) == (960, 540)
    assert draft_size((1920, 1080), scale=0.33) == (634, 356)
    assert draft_size((10, 10), scale=0.01) == (2, 2)
    assert draft_size((1920, 1080), size=(640, 361)) == (640, 361)    # as asked
    with pytest.raises(ValueError, match="not both"):
        draft_size((1920, 1080), 0.5, (640, 360))
    with pytest.raises(ValueError, match="positive"):
        draft_size((1920, 1080), scale=0)


def test_draft_frames_go_to_their_own_folder():
    shot = toy_shot()
    assert frame_folder("frames", shot, (64, 48)).name == "toy"
    assert frame_folder("frames", shot, (32, 24)).name == "toy@32x24"


def test_pixel_widths_scale_with_the_picture(toy_source):
    shot = toy_shot(layers=[{"type": "outline", "width": 3},
                            {"type": "body", "zero_width": 4, "opacity": 0.5}])
    full = Scene.make(shot, toy_source, VIEWS).values(0)
    half = Scene.make(shot, toy_source, VIEWS, size=(32, 24)).values(0)
    assert (full[0]["width"], full[1]["zero_width"]) == (3, 4)
    assert (half[0]["width"], half[1]["zero_width"]) == (1.5, 2)
    assert half[1]["opacity"] == 0.5                       # other options stay


def test_a_draft_render_leaves_the_full_frames_fresh(toy_source, tmp_path):
    def run(**kw):
        try:
            return render(toy_shot(), source=toy_source, views=VIEWS, out=tmp_path,
                          processes=False, **kw)
        except (RuntimeError, OSError) as error:
            pytest.skip(f"off-screen rendering is not available: {error}")

    run()
    draft = run(scale=0.5)
    assert draft.folder.name == "toy@32x24" and draft.count("rendered") == 3
    assert np.asarray(Image.open(draft.frames[0].path)).shape == (24, 32, 3)
    assert run().count("skipped") == 3
