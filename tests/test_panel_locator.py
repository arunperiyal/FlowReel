"""The locator panel: a body's span as a bar, its shape now, its supports, the windows."""
import numpy as np
import pytest
import yaml

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict
from flowreel.compose.span_panels import shape_at, window_at
from flowreel.scene.errors import ConfigError

from span_project import project
from test_panel_series import built


def shot(folder, name, crop):
    spec = {"name": name, "source": "flexflow", "time": {"steps": [0, 3]},
            "camera": {"view": "v"}, "crop": crop,
            "layers": [{"type": "outline", "bounds": "crop"}]}
    (folder / f"{name}.yml").write_text(yaml.safe_dump(spec))


def locator(folder, **options):
    project(folder)
    shot(folder, "travel", {"around": {"body": "pipe", "station": {"from": 2, "to": 8, "frames": [0, 3],
                                                                   "ease": "linear"}},
                            "half": [1, 2, 2]})
    shot(folder, "still", {"x": [4, 6], "y": [-1, 1], "z": [-1, 1]})
    spec = {"type": "locator", "size": [480, 120], "times": [0, 1, 2, 3], "body": "pipe",
            "shape": {"series": "span", "column": "dy", "amplify": 10},
            "windows": [{"shot": "travel.yml", "label": "window"},
                        {"shot": "still.yml", "colour": "#ff0000"}],
            "x": {"label": "span"}, **options}
    return from_dict(spec, file=str(folder / "loc.yml"))


def test_shape_at_a_time():
    t, s = np.array([0, 1.0]), np.array([0, 5.0])
    z = np.array([[0, 1.0], [0, 3.0]])
    xs, ys = shape_at(t, s, z, 0.25, amplify=10)
    assert xs.tolist() == [0, 5] and ys.tolist() == [0, 15]


def test_windows_of_each_frame(tmp_path):
    kind = panels.make(locator(tmp_path))
    travel, still = kind.windows
    assert [window_at(travel, i) for i in (0, 1, 3, 5)] == [(1, 3), (3, 5), (7, 9), (7, 9)]
    assert window_at(still, 2) == (4, 6) and still["colour"] == "#ff0000"


def test_built_and_moved(tmp_path):
    kind, fig = built(locator(tmp_path))
    (ax,) = fig.axes
    assert ax.get_xlim() == pytest.approx((-0.3, 10.3))          # the ends at 0 and 10
    # dy = 0.1 s t: at most 3 (station 10, time 3), amplified 10 times
    assert ax.get_ylim() == pytest.approx((-42, 42))
    kind.update(1.5, 2)
    xs, ys = kind.line.get_data()
    assert list(xs) == [0, 5, 10] and np.allclose(ys, [0, 7.5, 15])
    (box, text, _), (still, _, _) = kind.boxes
    assert (box.get_x(), box.get_width()) == (5, 2) and text.get_position()[0] == 6
    assert (still.get_x(), still.get_width()) == (4, 2)
    markers = [line.get_marker() for line in ax.lines if line is not kind.line]
    assert markers == ["^", "o"]                                  # pinned, roller
    assert len(ax.texts) == 2                                     # the label and the tension arrow


def test_without_shape_or_supports(tmp_path):
    kind, fig = built(locator(tmp_path, shape=None, supports=False, windows=None))
    (ax,) = fig.axes
    assert kind.line is None and ax.get_ylim() == pytest.approx((-1.4, 1.4)) and not ax.lines
    kind.update(0.0, 0)


def test_frames(tmp_path):
    rep = panels.panel(locator(tmp_path), tmp_path / "out", processes=False)
    assert rep.count("drawn") == 4


@pytest.mark.parametrize("change, msg", [
    ({"body": "pipes"}, r"body: no body 'pipes'"),
    ({"body": "rod", "shape": None, "windows": None}, r"body 'rod' declares no ends: give a 'shape'"),
    ({"shape": {"series": "span", "column": "dy", "amplify": 0}}, r"shape\.amplify: must be positive"),
    ({"windows": [{"shot": "none.yml"}]}, r"windows\[0\]\.shot: no shot file"),
    ({"supports": "yes"}, r"supports: expected true or false"),
])
def test_errors(tmp_path, change, msg):
    with pytest.raises(ConfigError, match=msg):
        panels.make(locator(tmp_path, **change))


def test_a_window_round_another_body(tmp_path):
    pf = locator(tmp_path)
    shot(tmp_path, "other", {"around": {"body": "rod", "station": 1}, "half": [1, 1, 1]})
    pf.options["windows"] = [{"shot": "other.yml"}]
    with pytest.raises(ConfigError, match=r"windows\[0\]\.shot: shot 'other' crops around 'rod', not 'pipe'"):
        panels.make(pf)
