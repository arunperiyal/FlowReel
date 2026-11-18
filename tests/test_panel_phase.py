"""The phase panel: one history against another, traced to the current time."""
import numpy as np
import pytest

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict
from flowreel.compose.phase_panel import phase_to_time
from flowreel.scene.errors import ConfigError

from panel_project import project
from test_panel_series import built


def phase(folder, **options):
    project(folder)
    spec = {"type": "phase", "size": [300, 300], "times": [0, 0.75, 2],
            "x": {"body": "bare", "series": "force", "column": "cl", "label": "$C_L$"},
            "y": {"series": "motion", "range": [-1, 5], "label": "$y$"}, **options}
    return from_dict(spec, file=str(folder / "ph.yml"))


def test_the_trace_takes_the_samples_of_both_series():
    tx, x = np.array([0, 1, 2.0]), np.array([0, 2, 4.0])
    ty, y = np.array([0, 0.5, 1.5]), np.array([0, 1, 3.0])
    xs, ys = phase_to_time(tx, x, ty, y, 1.25)
    assert xs.tolist() == [0, 1, 2, 2.5] and ys.tolist() == [0, 1, 2, 2.5]
    xs, ys = phase_to_time(tx, x, ty, y, 3)                      # after both: held
    assert (xs[-1], ys[-1]) == (4, 3)


def test_the_dot_is_at_the_current_values(tmp_path):
    kind, fig = built(phase(tmp_path))
    kind.update(0.75)                                           # CL = 2t, y = t^2 (sampled)
    assert kind.trace.get_xdata().tolist() == [0, 1, 1.5]
    assert kind.trace.get_ydata().tolist() == [0, 0.25, (0.25 + 1) / 2]
    assert (kind.dot.get_xdata()[0], kind.dot.get_ydata()[0]) == (1.5, 0.625)
    (ax,) = fig.axes
    assert ax.get_xlim() == pytest.approx((-0.48, 4.48)) and ax.get_ylim() == (-1, 5)
    assert ax.get_xlabel() == "$C_L$" and kind.trace.get_color() == kind.style.colours[0]


def test_frames(tmp_path):
    rep = panels.panel(phase(tmp_path, colour="white"), tmp_path / "out", processes=False)
    assert rep.count("drawn") == 3


@pytest.mark.parametrize("change, msg", [
    ({"y": None}, r"ph\.yml: missing key 'y'"),
    ({"x": {"series": "force", "body": "bare", "colour": "red"}}, r"x\.colour: unknown key"),
    ({"x": {"series": "force", "body": "bare", "range": [1]}}, r"x\.range: expected 2 numbers"),
    ({"colour": "nope"}, r"colour: expected a colour"),
])
def test_errors(tmp_path, change, msg):
    pf = phase(tmp_path, **change)
    if pf.options.get("y", 0) is None:
        del pf.options["y"]
    with pytest.raises(ConfigError, match=msg):
        panels.make(pf)
