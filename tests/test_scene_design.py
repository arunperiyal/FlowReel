"""The scene design window (Phase 10, branch 5): its state without a window, and the
window off screen, driven by synthetic mouse and key events."""
from pathlib import Path

import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel.editor.layout_state import DesignError, DesignState, inline
from flowreel.film import model as M

FILM = """\
# my film: its comments stay
fps: 24
size: [1920, 1080]
scenes:
  - name: opening          # the title card
    seconds: 4
    layout:
      boxes:
        - {name: title, text: 'Hello', place: centre}
    fade: [1, 1]
  - name: two
    seconds: 2
    layout: two
  - {name: flow, seconds: 2, layout: {boxes: [{text: a}]}}
"""


@pytest.fixture
def root(tmp_path):
    (tmp_path / "layouts").mkdir()
    (tmp_path / "layouts" / "two.yml").write_text("boxes: [{name: band, text: 'Two', place: top}]\n")
    (tmp_path / "film.yml").write_text(FILM)
    Image.new("RGB", (40, 20), (255, 0, 0)).save(tmp_path / "logo.png")
    return tmp_path


def boxes_of(root, scene):
    return [(b.name, b.kind, b.rect((1920, 1080))) for b in M.load(root / "film.yml").scene(scene).layout.boxes]


def test_moving_snaps_and_writes_in_place(root):
    s = DesignState.open(root / "film.yml", "opening")
    assert s.layout_file is None and s.rect("title") == (480, 270, 960, 540)
    s.move("title", 13, 4)        # x: no edge near 493, so the grid (500); y: its centre
    assert s.boxes[0]["pos"] == [500, 270] and "place" not in s.boxes[0]  # 544 snaps to 540
    s.move("title", -15, 0)       # its centre at 965, within 8 of the frame's 960
    assert boxes_of(root, "opening") == [("title", "text", (480, 270, 960, 540))]
    text = (root / "film.yml").read_text()
    assert "# my film: its comments stay" in text and "# the title card" in text
    assert "fade: [1, 1]" in text and "layout: two" in text


def test_a_box_drawn_resized_named_and_filled(root):
    s = DesignState.open(root / "film.yml", "opening")
    name = s.add(103, 98, 401, 305)
    assert name == "box1" and s.boxes[-1]["pos"] == [100, 100] and s.boxes[-1]["size"] == [300, 200]
    s.resize("box1", "bottom_right", 476, 333)             # 476 snaps to the title's 480
    assert s.boxes[-1]["size"] == [380, 240]
    s.rename("box1", "logo")
    s.fill("logo", "image", "logo.png")
    assert ("logo", "image", (100, 100, 380, 240)) in boxes_of(root, "opening")
    s.fill("title", "text", "Line one | Line two")
    assert M.load(root / "film.yml").scene("opening").layout.box("title").content.lines == \
        ("Line one", "Line two")


def test_edges_snap_to_other_boxes_and_the_grid_can_go(root):
    s = DesignState.open(root / "film.yml", "opening", grid=0)
    s.add(100, 100, 300, 200)
    s.move("box1", 77, 0)                       # right edge 377 ... no edge: stays, no grid
    assert s.boxes[-1]["pos"] == [177, 100]
    s.move("box1", 300, 0)                      # left 477: snaps to the title's left, 480
    assert s.boxes[-1]["pos"][0] == 480


def test_refused_changes_are_not_made(root):
    s = DesignState.open(root / "film.yml", "opening")
    before = (root / "film.yml").read_text()
    with pytest.raises(DesignError, match="no image file"):
        s.fill("title", "image", "missing.png")
    with pytest.raises(DesignError, match="at least 8 pixels"):
        s.add(100, 100, 102, 300)              # both x snap to 100
    with pytest.raises(DesignError, match="exists already"):
        s.add(0, 0, 100, 100, name="box1")
        s.rename("box1", "title")
    with pytest.raises(DesignError, match="keeps at least one box"):
        t = DesignState.open(root / "film.yml", "two")
        t.remove("band")
    assert "missing.png" not in (root / "film.yml").read_text()
    assert (root / "film.yml").read_text() != before          # the box1 added was written
    s.undo()
    assert (root / "film.yml").read_text().count("box1") == 0


def test_a_layout_file_and_a_scene_in_flow_style(root):
    s = DesignState.open(root / "film.yml", "two")
    assert s.layout_file == root / "layouts" / "two.yml"
    s.resize("band", "bottom_left", 200, 300)
    assert yaml.safe_load((root / "layouts" / "two.yml").read_text())["boxes"][0]["pos"] == [200, 0]
    f = DesignState.open(root / "film.yml", "flow")
    f.add(0, 0, 400, 400)
    assert [b[0] for b in boxes_of(root, "flow")] == ["text1", "box1"]
    assert "# my film: its comments stay" in (root / "film.yml").read_text()


def test_follow_boxes_are_placed_by_the_flow(root):
    (root / "shots").mkdir()
    (root / "shots" / "w.yml").write_text("{name: w, source: x, time: {frozen: 0}, layers: [{type: body}]}")
    s = DesignState.open(root / "film.yml", "opening")
    s.boxes = [{"name": "main", "shot": "shots/w.yml"},
               {"name": "label", "text": "here", "follow": {"box": "main", "model": [0, 0, 0]}}]
    s.write()
    with pytest.raises(DesignError, match="placed by the flow"):
        s.move("label", 10, 10)
    s.rename("main", "flow")
    assert s.boxes[1]["follow"]["box"] == "flow"


def test_inline_keeps_the_other_lines():
    text = "a: 1\nscenes:\n  - name: s\n    layout:\n      boxes: [{text: x}]\n    seconds: 2  # kept\n"
    out = inline(text, "s", {"boxes": [{"text": "y"}]})
    assert out.startswith("a: 1\nscenes:\n  - name: s\n    layout:\n") and "seconds: 2  # kept" in out
    assert yaml.safe_load(out)["scenes"][0]["layout"] == {"boxes": [{"text": "y"}]}


# ---- the window, off screen -----------------------------------------------------------

@pytest.fixture
def window(root):
    from flowreel.editor.design_window import DesignWindow
    w = DesignWindow(DesignState.open(root / "film.yml", "opening"), off_screen=True)
    yield w
    import matplotlib.pyplot as plt
    plt.close(w.fig)


def drag(w, a, b):
    from flowreel.editor.design_window import event
    w.on_press(event(w, *a))
    w.on_motion(event(w, *b))
    w.on_release(event(w, *b))


def test_the_window_draws_moves_and_resizes(window, root):
    w = window
    drag(w, (100, 100), (400, 300))                          # empty space: a new box
    assert w.state.selected == "box1" and w.state.boxes[-1]["size"] == [300, 200]
    drag(w, (200, 200), (260, 200))                           # inside it: moved
    assert w.state.boxes[-1]["pos"] == [160, 100]
    drag(w, (460, 300), (520, 360))                           # its bottom-right corner
    assert w.state.boxes[-1]["size"] == [360, 260]
    w.name_box.set_val("caption")
    w.kind.set_active(0)                                      # text
    w.content.set_val("Wake | behind the body")
    assert w.apply()
    box = M.load(root / "film.yml").scene("opening").layout.box("caption")
    assert box.content.lines == ("Wake", "behind the body")
    from flowreel.editor.design_window import event
    w.on_key(event(w, 0, 0, key="u"))
    assert M.load(root / "film.yml").scene("opening").layout.box("caption").content.lines == ("Text",)
    w.on_key(event(w, 0, 0, key="delete"))
    assert w.state.names() == ["title"]
    w.content.set_val("missing.png")
    w.select("title")
    w.kind.set_active(1)
    assert not w.apply() and "not done" in w.status.get_text()


def test_the_window_shows_the_scene_at_the_slider(window):
    w = window
    w.fig.canvas.draw()
    first = np.asarray(w.fig.canvas.buffer_rgba()).copy()
    assert w.picture().shape == (1080, 1920, 3)
    w.slider.set_val(2.0)
    assert w.time == 2.0 and "t = 2.00 s" in w.status.get_text()
    from flowreel.editor.design_window import event
    w.on_key(event(w, 0, 0, key="g"))
    assert w.state.grid == 0 and "grid off" in w.status.get_text()
    w.fig.canvas.draw()
    assert np.asarray(w.fig.canvas.buffer_rgba()).shape == first.shape
