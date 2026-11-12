"""The flexflow adapter on generated files: mesh types and body layouts the real test
case (bricks, one quadrilateral wall called ``cyl``) does not cover."""
import numpy as np
import pytest

from flowreel.sources import Source
from flowreel.sources.flexflow import FlexflowSource
from flowreel.sources.flexflow.plt import PltFile
from flowreel.sources.flexflow.plt_write import write_plt

VARS = ["X", "Y", "Z", "U", "V", "W", "Pressure", "xVor", "QCriterion"]
N = 4  # cells per side of the unit cube


def _node(i, j, k):
    return (k * (N + 1) + j) * (N + 1) + i


def cube(tets: bool, t: float = 0.0):
    """Nodes of a unit cube moved by ``t`` in z, its volume cells, and its bottom and top
    faces as triangles ("plate") and quadrilaterals ("lid")."""
    g = np.arange(N + 1) / N
    z, y, x = (a.ravel() for a in np.meshgrid(g, g, g, indexing="ij"))
    cols = [x, y, z + t, 1 + y, 2 * x, 3 * z, x + 10 * y, 0 * x + 99, 0 * x + 99]
    r = range(N)
    bricks = np.array([[_node(i, j, k), _node(i + 1, j, k), _node(i + 1, j + 1, k),
                        _node(i, j + 1, k), _node(i, j, k + 1), _node(i + 1, j, k + 1),
                        _node(i + 1, j + 1, k + 1), _node(i, j + 1, k + 1)]
                       for k in r for j in r for i in r])
    # six tetrahedra around the brick's 0-6 diagonal, all positively oriented
    split = [(0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)]
    volume = np.concatenate([bricks[:, s] for s in split]) if tets else bricks
    bottom = np.array([[_node(i, j, 0), _node(i + 1, j, 0), _node(i + 1, j + 1, 0),
                        _node(i, j + 1, 0)] for j in r for i in r])
    plate = np.concatenate([bottom[:, [0, 1, 2]], bottom[:, [0, 2, 3]]])
    lid = bottom + N * (N + 1) ** 2
    return cols, volume, plate, lid


def case(tmp_path, tets=True):
    for step, t in ((1, 0.0), (2, 0.5)):
        cols, volume, plate, lid = cube(tets, t)
        write_plt(tmp_path / f"flow.{step}.plt", VARS, cols,
                  [("fluid", 4 if tets else 5, volume), ("plate", 2, plate), ("lid", 3, lid)],
                  time=10.0 * step)
    return FlexflowSource(tmp_path)


def test_writer_round_trip(tmp_path):
    cols, volume, plate, lid = cube(True)
    write_plt(tmp_path / "a.1.plt", VARS, cols, [("fluid", 4, volume), ("plate", 2, plate)],
              title="made up", time=3.5)
    with PltFile(tmp_path / "a.1.plt") as plt:
        assert plt.title == "made up" and plt.vars == VARS
        assert [(z["name"], z["ztype"], z["time"]) for z in plt.zones] == \
            [("fluid", 4, 3.5), ("plate", 2, 3.5)]
        pts, conn, data, info = plt.load_zone(0)
        assert np.array_equal(conn, volume) and not info["truncated"]
        assert np.allclose(pts, np.column_stack(cols[:3]))
        assert np.allclose(data["Pressure"], cols[6])
        assert np.array_equal(plt.load_connectivity(1), plate)


def test_writer_refuses_bad_input(tmp_path):
    cols, volume, plate, _ = cube(True)
    with pytest.raises(ValueError, match="nodes per element"):
        write_plt(tmp_path / "a.plt", VARS, cols, [("fluid", 5, volume)])
    with pytest.raises(ValueError, match="outside"):
        write_plt(tmp_path / "a.plt", VARS, cols, [("fluid", 4, volume + 1000)])
    with pytest.raises(ValueError, match="one array per variable"):
        write_plt(tmp_path / "a.plt", VARS, cols[:-1], [("fluid", 4, volume)])


@pytest.mark.parametrize("tets", [True, False])
def test_zones_are_found_whatever_their_names(tmp_path, tets):
    src = case(tmp_path, tets)
    assert isinstance(src, Source)
    assert src.volume == "fluid" and src.bodies() == ["plate", "lid"]
    assert src.steps() == [1, 2] and src.time(2) == 20.0
    assert src.fields() == ["U", "V", "W", "p"]


@pytest.mark.parametrize("tets", [True, False])
def test_volume_cells_fill_the_cube(tmp_path, tets):
    g = case(tmp_path, tets).flow(1, ["U", "p"], None)
    assert g.n_cells == N ** 3 * (6 if tets else 1) and g.n_points == (N + 1) ** 3
    sizes = g.compute_cell_sizes()["Volume"]
    assert (sizes > 0).all() and sizes.sum() == pytest.approx(1.0)
    assert np.allclose(g.point_data["U"], 1 + g.points[:, 1])
    assert np.allclose(g.point_data["p"], g.points[:, 0] + 10 * g.points[:, 1], atol=1e-6)


def test_two_bodies_of_triangles_and_quads(tmp_path):
    src = case(tmp_path)
    plate, lid = src.body(1, "plate"), src.body(1, "lid")
    assert plate.n_cells == 2 * N * N and lid.n_cells == N * N
    assert np.allclose(plate.points[:, 2], 0) and np.allclose(lid.points[:, 2], 1)
    assert plate.area == pytest.approx(1.0) and lid.area == pytest.approx(1.0)
    both = src.body(1)
    assert both.n_cells == plate.n_cells + lid.n_cells and both.area == pytest.approx(2.0)
    assert np.allclose(src.body(2, "lid").points[:, 2], 1.5)       # bodies move with the step


def test_choosing_the_bodies(tmp_path):
    case(tmp_path)
    assert FlexflowSource(tmp_path, body="lid").bodies() == ["lid"]
    assert FlexflowSource(tmp_path, body=["lid", "plate"]).body(1).n_cells == 3 * N * N


def test_a_file_without_a_wall_has_no_body(tmp_path):
    cols, volume, _, _ = cube(False)
    write_plt(tmp_path / "flow.1.plt", VARS, cols, [("fluid", 5, volume)])
    src = FlexflowSource(tmp_path)
    assert src.bodies() == []
    with pytest.raises(LookupError):
        src.body(1)
