"""The map panel: a history at many points against time and station, filling in."""
import numpy as np
import pytest

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict
from flowreel.compose.span_panels import filled, span_table, symmetric
from flowreel.scene.errors import Checker, ConfigError

from span_project import T, lift, project
from test_panel_series import built


def mapping(folder, **options):
    project(folder)
    spec = {"type": "map", "size": [480, 360], "times": [0, 1.5, 3],
            "rows": [{"body": "pipe", "series": "span", "column": "cl", "title": "pipe"},
                     {"body": "rod", "series": "span", "title": "rod", "colour": "#ff0000"}],
            "y": {"label": "span", "ticks": [0, 5, 10]}, "range": [-1, 1],
            "colorbar": {"label": "$C_L$"}, **options}
    return from_dict(spec, file=str(folder / "map.yml"))


def test_the_table(tmp_path):
    kind = panels.make(mapping(tmp_path))
    t, s, z = span_table(kind.rows[0][0], Checker())
    assert t.tolist() == T.tolist() and s.tolist() == [0, 5, 10]
    assert np.allclose(z, lift(T[:, None], s[None, :]))
    t, s, z = span_table(kind.rows[1][0], Checker())          # no stations: point numbers
    assert s.tolist() == [1, 2] and z[3].tolist() == [7, 8]


def test_filling_in_to_a_time():
    t, z = np.array([0, 1, 2.0]), np.array([[1, 2], [3, 4], [5, 6.0]])
    shown = filled(t, z, 1.0)
    assert shown.shape == (2, 3)
    assert shown[:, :2].tolist() == [[1, 3], [2, 4]] and np.isnan(shown[:, 2]).all()
    assert np.isnan(filled(t, z, -0.5)).all() and not np.isnan(filled(t, z, 9)).any()


def test_built_and_moved(tmp_path):
    kind, fig = built(mapping(tmp_path))
    ax0, ax1, bar = fig.axes
    assert ax0.get_xlim() == (0, 3) and list(ax0.get_yticks()) == [0, 5, 10]
    assert ax0.get_title(loc="left") == "pipe" and ax1.get_title(loc="left") == "rod"
    assert ax1._left_title.get_color() == "#ff0000"
    assert bar.get_ylabel() == "$C_L$"
    kind.update(1.5)
    image, t, z = kind.images[0]
    a = np.asarray(image.get_array()).reshape(3, 4)            # station by time
    assert np.allclose(a[:, :2], z[:2].T) and np.isnan(a[:, 2:]).all()
    assert image.get_clim() == (-1, 1)


def test_default_range_is_symmetric(tmp_path):
    assert symmetric([np.array([[-0.5, 2.0]]), np.array([[np.nan, -3.0]])]) == (-3.0, 3.0)
    pf = mapping(tmp_path, range=None, colorbar=False)
    kind, fig = built(pf)
    assert len(fig.axes) == 2 and kind.images[1][0].get_clim() == (-8, 8)   # rod: 2t + n, at most 8


def test_frames(tmp_path):
    rep = panels.panel(mapping(tmp_path), tmp_path / "out", processes=False)
    assert rep.count("drawn") == 3


@pytest.mark.parametrize("change, msg", [
    ({"rows": [{"body": "pipe", "series": "force"}]}, r"is at one point; declare it with 'by'"),
    ({"rows": [{"body": "pipe", "series": "span"}]}, r"series 'span' has columns cl, dy; say which"),
    ({"rows": [{"body": "pipe", "series": "span", "column": "cd"}]}, r"rows\[0\]\.column: series 'span' has no column 'cd'"),
])
def test_errors_when_reading(tmp_path, change, msg):
    with pytest.raises(ConfigError, match=msg):
        built(mapping(tmp_path, **change))


@pytest.mark.parametrize("change, msg", [
    ({"rows": []}, r"rows: expected at least 1"),
    ({"colormap": "fire"}, r"colormap: unknown colormap 'fire'"),
    ({"range": [1, 0]}, r"range: expected \[low, high\]"),
    ({"colorbar": {"lable": "x"}}, r"colorbar\.lable: unknown key"),
    ({"y": {"ticks": ["a"]}}, r"y\.ticks\[0\]: expected a number"),
    ({"rows": [{"body": "pipe", "series": "span", "label": "x"}]}, r"rows\[0\]\.label: unknown key"),
])
def test_errors(tmp_path, change, msg):
    with pytest.raises(ConfigError, match=msg):
        panels.make(mapping(tmp_path, **change))
