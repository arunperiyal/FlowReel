"""The strip panel (compose/flow_panels.py) on the generated cylinder case."""
import sys
from pathlib import Path

import numpy as np
import pytest
from matplotlib.figure import Figure
from PIL import Image

from flowreel.compose import panel
from flowreel.compose.flow_panels import axis_points
from flowreel.compose.panel_file import from_dict
from flowreel.compose.panels import make
from flowreel.scene.errors import ConfigError

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "flow_panels"))
import cylinder_case as case  # noqa: E402

TIMES = [0.0, 0.5, 1.0, 1.5]
MU = 0.5


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return case.write_case(tmp_path_factory.mktemp("cylinder"))


def strip(folder, **spec):
    base = {"type": "strip", "size": [640, 180], "times": TIMES,
            "source": {"adapter": "flexflow", "path": "case", "cache": None},
            "side": "y", "field": "p", "range": [-1, 1]}
    return from_dict({**base, **spec}, file=str(folder / "strip.yml"))


def test_seen_from_one_side_span_across_not_mirrored(folder):
    kind = make(strip(folder))
    assert np.allclose(kind.up, [0, 0, -1])                     # from +y, x right: z down
    assert np.allclose(make(strip(folder, side="-y")).up, [0, 0, 1])
    assert np.allclose(make(strip(folder, side="z")).up, [0, 1, 0])
    s = kind.state(1.0)
    assert s["step"] == 20
    surf = kind.surface(20)
    pts = np.asarray(surf.points)
    middle = pts[s["triangles"]].mean(axis=1)
    assert len(s["triangles"]) == surf.n_cells // 2               # the near half
    assert (middle[:, 1] > case.centre_y(1.0)).all()
    assert np.allclose(s["across"], pts[:, 0]) and np.allclose(s["up"], -pts[:, 2])


def test_a_field_on_the_wall_is_taken_as_it_is(folder):
    s = make(strip(folder)).state(0.5)
    assert np.allclose(s["values"], -case.SLOPE * s["up"], atol=1e-5)        # p = z


def test_wall_shear_and_its_zero_line(folder):
    kind = make(strip(folder, field="wall_shear", component="x", params={"mu": MU},
                      range=[-0.3, 0.3]))
    s = kind.state(1.5)
    pts = np.asarray(kind.surface(30).points)
    theta = np.arctan2(pts[:, 2], pts[:, 1] - case.centre_y(1.5))
    inner = (pts[:, 0] > 0.1) & (pts[:, 0] < case.SPAN - 0.1)     # ends average fewer cells
    exact = MU * case.SHEAR * np.sin(theta)
    assert np.abs(s["values"][inner] - exact[inner]).max() < 0.01 * MU * case.SHEAR
    kind.build(Figure())
    kind.update(1.5, 3)
    seg = np.concatenate(kind.zero_line.allsegs[0])
    inside = (seg[:, 0] > 0.6) & (seg[:, 0] < case.SPAN - 0.6)
    assert np.abs(seg[inside, 1]).max() < 1e-3                   # along z = 0


def test_a_flow_field_is_sampled_on_the_wall(folder):
    s = make(strip(folder, field="vorticity_x", range=[0, 2])).state(0.0)
    used = np.unique(s["triangles"])
    assert np.allclose(s["values"][used], 2 * case.OMEGA, atol=1e-3)


def test_span_cuts_the_body(folder):
    kind = make(strip(folder, span=[1, 3]))
    s = kind.state(0.0)
    assert s["across"].min() >= 1 - 1e-6 and s["across"].max() <= 3 + 1e-6
    kind.build(Figure())
    kind.update(0.0, 0)
    assert kind.ax.get_xlim() == (1, 3)


def test_axis_points_skip_empty_slices():
    pts = np.array([[0, 1, 0], [0, -1, 0], [10, 3, 0], [10, 1, 0]], float)
    out = axis_points(pts, 0, np.array([0.0, 5.0, 10.0]))
    assert np.allclose(out[:, 1], [0, 1, 2])


def test_draws(folder):
    report = panel(strip(folder, field="wall_shear", component="x", params={"mu": MU},
                         range=[-0.3, 0.3]), folder / "frames", processes=False)
    assert report.count("drawn") == 4
    picture = np.asarray(Image.open(report.frames[0][1]))
    assert picture.shape == (180, 640, 3) and picture.std() > 10


def test_errors(folder):
    with pytest.raises(ConfigError, match="'side'"):
        make(strip(folder, side=None))
    with pytest.raises(ConfigError, match="body's axis"):
        make(strip(folder, side="-x"))
    with pytest.raises(ConfigError, match="span"):
        make(strip(folder, span=[3, 1]))
    kind = make(strip(folder, field="wall_shear", params={"mu": MU}))
    kind.build(Figure())
    with pytest.raises(ConfigError, match="vector.*component"):
        kind.update(0.0, 0)
    kind = make(strip(folder, component="x"))
    kind.build(Figure())
    with pytest.raises(ConfigError, match="not a vector"):
        kind.update(0.0, 0)
    kind = make(strip(folder, field="wall_shear", component="x"))
    kind.build(Figure())
    with pytest.raises(ConfigError, match="mu"):
        kind.update(0.0, 0)
