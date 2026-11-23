"""Phase 2B's check: a case of a riser 500 diameters long, generated at test time
(examples/riser500/riser500_case.py), read by declared name and by window."""
import sys
from pathlib import Path

import numpy as np
import pytest

from flowreel.box import Box
from flowreel.project import load_project
from flowreel.project.measure import diameter, long_axis
from flowreel.sources.plt import PltSource

sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "riser500"))
import riser500_case as case  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return case.write_case(tmp_path_factory.mktemp("riser500"))


def test_the_case_is_a_riser_500_long_and_a_second_body(folder):
    source = PltSource(folder / "case", cache=None)
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
    source = declare(PltSource(folder / "case", cache=None), load_project(folder))
    disp = source.series("displacement", body="riser")
    assert disp.node.nunique() == case.PROBES
    assert (disp.station.min(), disp.station.max()) == (0, 500)
    row = disp[np.isclose(disp.time, 1.0) & np.isclose(disp.station, 50)]
    assert row.dy.item() == pytest.approx(case.displacement(50, 1.0))
    swing = source.series("swing", body="pendulum")
    assert swing.pendDisp.abs().max() == pytest.approx(case.SWING, rel=0.01)


def test_the_three_shots_read_the_case(folder):
    from flowreel.scene.rendering import Scene
    travel = Scene.make(folder / "travel.yml")
    assert travel.plan.n_frames == case.STEPS
    boxes = [travel.crop(i) for i in (0, case.STEPS - 1)]
    assert [b.lo[0] + 10 for b in boxes] == pytest.approx([20, 480], abs=0.05)
    span = Scene.make(folder / "span.yml")
    assert span.shot.stretch.scale == (0.02, 1.0, 1.0) and span.shot.crop is None
    pendulum = Scene.make(folder / "pendulum.yml")
    assert pendulum.crop(3).lo[0] == pytest.approx(244, abs=0.05)
    assert pendulum.source.is_virtual("pendulum")


@pytest.mark.parametrize("shot", ["travel", "span", "pendulum"])
def test_the_frames_render(folder, tmp_path, shot):
    from flowreel.scene import render
    try:
        report = render(folder / f"{shot}.yml", [0, 3, 7], out=tmp_path, jobs=1, scale=0.5)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert report.count("rendered") == 3                  # first, middle and last
    frames = sorted(report.folder.glob("*.png"))
    assert len(frames) == 3
    from PIL import Image
    img = np.asarray(Image.open(frames[1]))
    assert img.shape[:2] == (180, 320) and img.std() > 10


def test_the_window_reads_a_small_part_of_the_file(folder):
    from flowreel.scene.rendering import Scene
    travel = Scene.make(folder / "travel.yml")
    source = travel.source
    whole = PltSource(folder / "case", cache=None)
    total = 1000 * 8 * 8
    for i in (0, 4, 7):
        cells = travel.data(i).flow.n_cells
        box = travel.crop(i)
        assert 0.75 * 40 * 8 * 8 <= cells <= 40 * 8 * 8  # 20 long; a row less when it moves
        flow = travel.data(i).flow
        assert flow.bounds[0] >= box.lo[0] - 1e-6 and flow.bounds[1] <= box.hi[0] + 1e-6
        assert len(source.window_of(box).cells) < 0.06 * total     # with the margin
    assert whole.memory_per_step(None) > 20 * source.memory_per_step(travel.crop(0))


def test_the_window_does_not_grow_with_the_span(folder, tmp_path):
    """The Phase 2B check: the same window costs the same in a case half as long."""
    half = case.write_case(tmp_path / "half", length=250.0, project=False)
    long = PltSource(folder / "case", cache=None, margin=1.0)
    short = PltSource(half / "case", cache=None, margin=1.0)
    box = Box((90, -4, -4), (110, 4, 4))
    assert long.memory_per_step(box) == pytest.approx(short.memory_per_step(box))
    assert long.memory_per_step(None) == pytest.approx(2 * short.memory_per_step(None), rel=0.02)
    assert long.flow(3, ["U"], box).n_cells == short.flow(3, ["U"], box).n_cells


def test_the_pendulum_follows_its_series(folder):
    from flowreel.scene.rendering import Scene
    sc = Scene.make(folder / "pendulum.yml")
    for i in range(sc.plan.n_frames):
        step = sc.plan.time.step(i)
        t = sc.source.time(step)
        pivot = np.asarray(sc.source.origin(step, "pendulum"))
        assert pivot[0] == pytest.approx(250) and pivot[2] == pytest.approx(0, abs=1e-6)
        assert pivot[1] == pytest.approx(case.displacement(250, t), abs=0.02)
        points = np.asarray(sc.data(i).body("pendulum").points) - pivot
        far = points[np.argmax(np.linalg.norm(points, axis=1))]   # the bob's far side
        angle = np.arctan2(far[0], -far[1])           # turned about z: along x, from down
        assert angle == pytest.approx(case.swing(t), abs=0.03)
