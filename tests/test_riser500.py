"""Phase 2B's check: a case of a riser 500 diameters long, generated at test time
(examples/riser500/riser500_case.py), read by declared name and by window."""
import sys
from pathlib import Path

import numpy as np
import pytest

from flowreel.box import Box
from flowreel.project import load_project
from flowreel.project.measure import diameter, long_axis
from flowreel.sources.flexflow import FlexflowSource

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "riser500"))
import riser500_case as case  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return case.write_case(tmp_path_factory.mktemp("riser500"))


def test_the_case_is_a_riser_500_long_and_a_second_body(folder):
    source = FlexflowSource(folder / "case", cache=None)
    assert source.steps() == list(range(case.STEPS))
    assert source.time(3) == pytest.approx(3 * case.DT)
    assert source.bodies() == ["cyl", "cyl2"] and source.volume == "fluid"
    riser = source.body(0, "cyl")
    assert np.ptp(riser.points[:, 0]) == pytest.approx(500)
    assert long_axis(riser) == "x" and diameter(riser, "x") == pytest.approx(1, abs=0.02)
    other = source.body(0, "cyl2")
    assert np.ptp(other.points[:, 0]) == pytest.approx(12)
    moved = source.body(1, "cyl")                         # the third mode, at t = 0.5
    at = np.isclose(moved.points[:, 0], 250 / 3 * 0.5, atol=0.13)
    assert moved.points[at, 1].mean() == pytest.approx(case.displacement(250 / 6, 0.5), abs=0.02)


def test_the_project_declares_supports_tension_and_series(folder):
    bodies = load_project(folder).bodies
    assert sorted(bodies) == ["downstream", "pendulum", "riser"]
    riser = bodies["riser"]
    assert [(e.at, e.support, e.tension) for e in riser.ends] == [
        (0.0, "pinned", False), (500.0, "roller", True)]
    assert bodies["pendulum"].virtual and bodies["pendulum"].attach.station == 250
    from flowreel.project.names import declare
    source = declare(FlexflowSource(folder / "case", cache=None), load_project(folder))
    disp = source.series("displacement", body="riser")
    assert disp.node.nunique() == case.PROBES
    assert (disp.station.min(), disp.station.max()) == (0, 500)
    row = disp[np.isclose(disp.time, 1.0) & np.isclose(disp.station, 50)]
    assert row.dy.item() == pytest.approx(case.displacement(50, 1.0))
    swing = source.series("swing", body="pendulum")
    assert swing.pendDisp.abs().max() == pytest.approx(case.SWING, rel=0.01)
