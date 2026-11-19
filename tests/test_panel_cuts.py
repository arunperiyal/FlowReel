"""The cuts panel (compose/flow_panels.py) on the generated cylinder case."""
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.compose import panel
from flowreel.compose.panel_file import from_dict
from flowreel.compose.panels import make
from flowreel.scene.errors import ConfigError

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

TIMES = [0.0, 0.5, 1.0, 1.5]


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return case.write_case(tmp_path_factory.mktemp("cylinder"))


def cuts(folder, **spec):
    base = {"type": "cuts", "size": [600, 200], "times": TIMES,
            "source": {"adapter": "flexflow", "path": "case", "cache": None},
            "stations": [1.0, 2.0, 3.0], "field": "p", "range": [-2, 2]}
    return from_dict({**base, **spec}, file=str(folder / "cuts.yml"))


def test_each_station_is_its_own_cut_round_the_body(folder):
    kind = make(cuts(folder))
    s = kind.state(1.0)
    assert s["step"] == 20 and [v[0] for v in s["views"]] == [1.0, 2.0, 3.0]
    for station, centre, cut, curves, crop in s["views"]:
        assert np.allclose(centre, [case.centre_y(1.0), 0], atol=1e-6)
        assert crop.lo[0] == pytest.approx(station - 1.0)              # depth: one diameter
        assert crop.hi[0] == pytest.approx(station + 1.0)
        assert np.allclose(cut.values["p"], case.SLOPE * cut.points[:, 1], atol=1e-5)
        assert len(curves) == 1


def test_fixed_centre_and_side_by_side(folder):
    kind = make(cuts(folder, centre=[0, 0], half=[2, 1], gap=0.01))
    assert all(np.allclose(v[1], [0, 0]) for v in kind.state(0.0)["views"])
    rects = kind.rects()
    assert rects[0][0] == 0 and rects[-1][0] + rects[-1][2] == pytest.approx(1)
    assert rects[1][0] - (rects[0][0] + rects[0][2]) == pytest.approx(0.01)
    assert rects[0][1] == pytest.approx(0.09)                     # room for the labels
    assert make(cuts(folder, label=False)).rects()[0][1] == 0


def test_draws_labelled_frames(folder):
    report = panel(cuts(folder, label="x = {station:g} D"), folder / "frames", processes=False)
    assert report.count("drawn") == 4
    picture = np.asarray(Image.open(report.frames[1][1]))
    assert picture.shape == (200, 600, 3) and picture.std() > 10
    kind = make(cuts(folder, label="x = {station:g} D"))
    from matplotlib.figure import Figure
    kind.build(Figure())
    kind.update(0.0, 0)
    assert [t.get_text() for ax in kind.axes_list for t in ax.texts] == \
        ["x = 1 D", "x = 2 D", "x = 3 D"]


def test_errors(folder):
    with pytest.raises(ConfigError, match="stations"):
        make(cuts(folder, stations=None))
    with pytest.raises(ConfigError, match=r"label.*\{station\}"):
        make(cuts(folder, label="{where}"))
    with pytest.raises(ConfigError, match="gap"):
        make(cuts(folder, gap=0.6))
