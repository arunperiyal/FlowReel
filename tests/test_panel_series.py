"""The series panel: lines to the current time, ending at a dot at the interpolated value."""
import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from PIL import Image

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict
from flowreel.compose.series_panel import padded, to_time
from flowreel.scene.errors import ConfigError

from panel_project import project

ROWS = [{"label": "$C_L$", "lines": [{"body": "bare", "series": "force", "column": "cl",
                                      "label": "bare"},
                                     {"body": "helical", "series": "force", "column": "cl",
                                      "label": "helical", "colour": "#ff0000"}]},
        {"label": "$y$", "range": [-1, 5], "lines": [{"series": "motion"}]}]


def series(folder, **options):
    project(folder)
    spec = {"type": "series", "size": [320, 360], "times": [0, 0.25, 1.75, 3],
            "x": {"label": "$t$"}, "rows": ROWS, **options}
    return from_dict(spec, file=str(folder / "lift.yml"))


def built(pf):
    kind = panels.make(pf)
    with pf.style.applied():
        fig = Figure(figsize=(pf.size[0] / 100, pf.size[1] / 100), dpi=100)
        FigureCanvasAgg(fig)
        kind.build(fig)
    return kind, fig


def test_a_line_to_a_time_between_samples():
    t, v = np.array([0, 1, 2.0]), np.array([0, 10, 30.0])
    xs, ys = to_time(t, v, 1.25)
    assert xs.tolist() == [0, 1, 1.25] and ys.tolist() == [0, 10, 15]
    xs, ys = to_time(t, v, 1.0)                     # on a sample: it ends there, once
    assert xs.tolist() == [0, 1] and ys.tolist() == [0, 10]
    xs, ys = to_time(t, v, 5.0)                     # after the last: held
    assert xs.tolist() == [0, 1, 2, 5] and ys.tolist() == [0, 10, 30, 30]


def test_lines_and_dots(tmp_path):
    kind, fig = built(series(tmp_path))
    kind.update(1.75)
    (bare, bare_dot, *_), (hel, hel_dot, *_), (mot, mot_dot, *_) = kind.artists
    assert bare.get_xdata().tolist() == [0, 0.5, 1, 1.5, 1.75]
    assert bare.get_ydata().tolist() == [0, 1, 2, 3, 3.5]               # CL = 2t
    assert (bare_dot.get_xdata()[0], bare_dot.get_ydata()[0]) == (1.75, 3.5)
    assert hel_dot.get_ydata()[0] == -1.75 and hel.get_color() == "#ff0000"
    assert mot_dot.get_ydata()[0] == pytest.approx((2.25 + 4) / 2)      # between 1.5^2 and 2^2
    assert bare.get_color() == kind.style.colours[0]


def test_axes(tmp_path):
    kind, fig = built(series(tmp_path))
    top, bottom = fig.axes
    assert top.get_xlim() == (0, 3) and bottom.get_xlim() == (0, 3)     # shared, the times
    assert top.get_ylim() == pytest.approx(padded([np.array([0, 4.0]), np.array([-2, 0.0])], 0.12))
    assert top.get_ylim() == pytest.approx((-2.72, 4.72))
    assert bottom.get_ylim() == (-1, 5) and bottom.get_xlabel() == "$t$"
    assert [t.get_text() for t in top.get_legend().get_texts()] == ["bare", "helical"]


def test_one_row_and_an_x_range(tmp_path):
    pf = series(tmp_path, rows=None, x={"range": [0, 2]}, y={"label": "$C_D$"},
                lines=[{"body": "bare", "series": "force", "column": "cd"}], legend=False)
    kind, fig = built(pf)
    (ax,) = fig.axes
    assert ax.get_xlim() == (0, 2) and ax.get_ylabel() == "$C_D$" and ax.get_legend() is None


def test_frames_in_processes(tmp_path):
    pf = series(tmp_path)
    rep = panels.panel(pf, tmp_path / "out", jobs=2)
    assert rep.count("drawn") == 4
    im = Image.open(rep.frames[2][1])
    assert im.size == (320, 360)
    assert panels.panel(pf, tmp_path / "out", jobs=2).count("skipped") == 4


@pytest.mark.parametrize("change, msg", [
    ({"rows": [{"lines": [{"series": "force"}]}]}, r"rows\[0\]\.lines\[0\]: series 'force' is declared for bare, helical"),
    ({"rows": [{"lines": [{"body": "pipe", "series": "force"}]}]}, r"lines\[0\]\.body: no body 'pipe'"),
    ({"rows": [{"lines": [{"body": "bare", "series": "lift"}]}]}, r"lines\[0\]\.series: body 'bare' has no series 'lift'"),
    ({"rows": [{"lines": [{"body": "bare", "series": "force", "colour": "#1"}]}]}, r"lines\[0\]\.colour"),
    ({"rows": [], }, r"rows: expected at least 1"),
    ({"rows": None}, r"missing key 'rows'"),
    ({"x": {"range": [2, 1]}}, r"x\.range: expected \[low, high\]"),
    ({"margins": {"left": 0.9, "right": 0.5}}, r"margins: expected 0 <= left < right"),
    ({"legend": "yes"}, r"legend: expected true or false"),
])
def test_errors(tmp_path, change, msg):
    spec = {"type": "series", "times": [0], "rows": ROWS, **change}
    if spec["rows"] is None:
        del spec["rows"]
    project(tmp_path)
    with pytest.raises(ConfigError, match=msg):
        panels.make(from_dict(spec, file=str(tmp_path / "p.yml")))


@pytest.mark.parametrize("line, msg", [
    ({"body": "bare", "series": "force"}, r"series 'force' has columns cl, cd; say which"),
    ({"body": "bare", "series": "force", "column": "cm"}, r"column: series 'force' has no column 'cm'"),
    ({"body": "helical", "series": "span"}, r"is at many points; draw it with a map panel"),
])
def test_errors_when_reading(tmp_path, line, msg):
    pf = series(tmp_path, rows=[{"lines": [line]}])
    with pytest.raises(ConfigError, match=msg):
        built(pf)


def test_no_project(tmp_path):
    with pytest.raises(ConfigError, match="no flowreel.yml"):
        panels.make(from_dict({"type": "series", "times": [0], "rows": ROWS},
                              file=str(tmp_path / "a" / "p.yml")))
