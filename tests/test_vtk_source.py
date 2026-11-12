"""The vtk adapter, on small files generated into tmp_path."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.box import Box
from flowreel.sources import Source
from flowreel.sources.vtk import VtkSource

STEPS = (10, 20, 30)


def grid(step):
    """A 4x4x2-cell block; U grows with the step so steps can be told apart."""
    g = pv.ImageData(dimensions=(5, 5, 3)).cast_to_unstructured_grid()
    x, y, z = g.points.T
    g.point_data["velocity"] = np.column_stack([step * y, -x, 0.5 * z])
    g.point_data["pressure"] = x + y
    g.point_data["T"] = z
    return g


@pytest.fixture
def series(tmp_path):
    """Three .vtu files, a .pvd listing them (times 1, 2, 3) and a body file."""
    lines = []
    for step in STEPS:
        grid(step).save(tmp_path / f"wake_{step:04d}.vtu")
        lines.append(f'<DataSet timestep="{step / 10}" part="0" file="wake_{step:04d}.vtu"/>')
    (tmp_path / "wake.pvd").write_text(
        '<?xml version="1.0"?>\n<VTKFile type="Collection" version="0.1">\n<Collection>\n'
        + "\n".join(lines) + "\n</Collection>\n</VTKFile>\n")
    pv.Sphere(radius=0.3, center=(2, 2, 1)).save(tmp_path / "body.vtp")
    return tmp_path


def test_satisfies_protocol(series):
    assert isinstance(VtkSource(series / "wake_*.vtu"), Source)


def test_pattern_steps_from_filename_and_time_is_step(series):
    src = VtkSource(series / "wake_*.vtu")
    assert src.steps() == [10, 20, 30]
    assert src.time(20) == 20.0


def test_pattern_dt_and_times(series):
    assert VtkSource(series / "wake_*.vtu", dt=0.5).time(30) == 15.0
    assert VtkSource(series / "wake_*.vtu", times=[0.1, 0.2, 0.4]).time(30) == 0.4
    assert VtkSource(series / "wake_*.vtu", times={10: 1, 20: 2, 30: 5}).time(30) == 5.0
    with pytest.raises(ValueError, match="times"):
        VtkSource(series / "wake_*.vtu", times=[0.1, 0.2])


def test_pvd_steps_are_indices_and_times_come_from_the_file(series):
    src = VtkSource(series / "wake.pvd")
    assert src.steps() == [0, 1, 2]
    assert [src.time(s) for s in src.steps()] == [1.0, 2.0, 3.0]
    assert np.allclose(src.flow(2, ["U"], None)["U"], grid(30)["velocity"][:, 0])


def test_single_file_is_step_zero(series):
    assert VtkSource(series / "wake_0010.vtu").steps() == [0]


def test_missing_files_and_steps(series):
    with pytest.raises(FileNotFoundError):
        VtkSource(series / "nothing_*.vtu")
    with pytest.raises(FileNotFoundError):
        VtkSource(series / "nothing.pvd")
    with pytest.raises(KeyError, match="no step 15"):
        VtkSource(series / "wake_*.vtu").time(15)


def test_fields_use_standard_names(series):
    assert VtkSource(series / "wake_*.vtu").fields() == ["U", "V", "W", "velocity", "p", "T"]


def test_flow_splits_velocity_and_maps_pressure(series):
    g = VtkSource(series / "wake_*.vtu").flow(20, ["U", "V", "W", "p", "velocity", "T"], None)
    ref = grid(20)
    assert isinstance(g, pv.UnstructuredGrid)
    assert list(g.point_data.keys()) == ["U", "V", "W", "p", "velocity", "T"]
    for i, c in enumerate("UVW"):
        assert np.allclose(g[c], ref["velocity"][:, i])
    assert np.allclose(g["p"], ref["pressure"])
    assert np.allclose(g["velocity"], ref["velocity"])


def test_flow_returns_requested_fields_only(series):
    g = VtkSource(series / "wake_*.vtu").flow(10, ["V"], None)
    assert g.array_names == ["V"]


def test_unknown_field_lists_available(series):
    with pytest.raises(KeyError, match="available"):
        VtkSource(series / "wake_*.vtu").flow(10, ["Q"], None)


def test_names_option_maps_scalar_components(tmp_path):
    g = grid(1)
    for i, own in enumerate(("ux", "uy", "uz")):
        g.point_data[own] = g["velocity"][:, i]
    g.point_data["pres"] = g["pressure"]
    del g.point_data["velocity"], g.point_data["pressure"]
    g.save(tmp_path / "a_1.vtu")
    names = {"U": "ux", "V": "uy", "W": "uz", "p": "pres"}
    src = VtkSource(tmp_path / "a_*.vtu", names=names)
    assert src.fields() == ["U", "V", "W", "velocity", "p", "T"]
    out = src.flow(1, ["velocity", "p", "W"], None)
    assert np.allclose(out["velocity"], grid(1)["velocity"])
    assert np.allclose(out["p"], grid(1)["pressure"])
    with pytest.raises(ValueError, match="names"):
        VtkSource(tmp_path / "a_*.vtu", names={"pressure": "pres"})


def test_names_option_maps_a_vector(tmp_path):
    g = grid(1)
    g.point_data["vel"] = g["velocity"]
    del g.point_data["velocity"]
    g.save(tmp_path / "a_1.vtu")
    src = VtkSource(tmp_path / "a_*.vtu", names={"velocity": "vel"})
    assert np.allclose(src.flow(1, ["V"], None)["V"], -g.points[:, 0])


def test_cell_arrays_are_moved_to_points(tmp_path):
    g = grid(1).point_data_to_cell_data()
    g.save(tmp_path / "c_1.vtu")
    out = VtkSource(tmp_path / "c_*.vtu").flow(1, ["p"], None)
    assert out["p"].shape == (out.n_points,)
    assert out.cell_data.keys() == []


def test_crop_keeps_cells_with_every_node_inside(series):
    src = VtkSource(series / "wake_*.vtu")
    box = Box((0, 0, 0), (2.5, 4, 2))  # x nodes 0, 1, 2 are inside: 2 of 4 cells in x
    g = src.flow(10, ["U", "p"], box)
    assert g.n_cells == 2 * 4 * 2
    assert box.contains(g.points).all()
    assert g.array_names == ["U", "p"]
    assert np.allclose(g["p"], g.points[:, 0] + g.points[:, 1])  # data follows the points


def test_crop_outside_the_domain_is_empty(series):
    g = VtkSource(series / "wake_*.vtu").flow(10, ["U"], Box((10, 10, 10), (11, 11, 11)))
    assert g.n_cells == 0


def test_bounds(series):
    assert VtkSource(series / "wake.pvd").bounds() == Box((0, 0, 0), (4, 4, 2))


def test_memory_per_step_shrinks_with_the_crop(series):
    src = VtkSource(series / "wake_*.vtu")
    full = src.memory_per_step(None)
    half = src.memory_per_step(Box((0, 0, 0), (2, 4, 2)))
    assert 0 < half < full < 1e-3
    assert src.memory_per_step(Box((10, 10, 10), (11, 11, 11))) == 0


def test_body_from_one_file_serves_every_step(series):
    src = VtkSource(series / "wake_*.vtu", body=series / "body.vtp")
    body = src.body(30)
    assert isinstance(body, pv.PolyData)
    assert np.allclose(body.center, (2, 2, 1), atol=1e-3)


def test_body_from_a_pattern_follows_the_step(series):
    for step in STEPS:
        pv.Sphere(radius=step / 100).save(series / f"cyl_{step:04d}.vtp")
    src = VtkSource(series / "wake_*.vtu", body=series / "cyl_*.vtp")
    assert src.body(30).bounds[5] == pytest.approx(0.3)
    assert src.body(10).bounds[5] == pytest.approx(0.1)


def test_body_from_a_volume_file_is_its_surface(series):
    pv.ImageData(dimensions=(3, 3, 3)).cast_to_unstructured_grid().save(series / "solid.vtu")
    body = VtkSource(series / "wake_*.vtu", body=series / "solid.vtu").body(10)
    assert isinstance(body, pv.PolyData)
    assert body.n_cells == 6 * 4


def test_body_from_a_named_block(tmp_path):
    for step in (1, 2):
        pv.MultiBlock({"fluid": grid(step), "wall": pv.Sphere(radius=step)}).save(
            tmp_path / f"mb_{step}.vtm")
    src = VtkSource(tmp_path / "mb_*.vtm", body_block="wall")
    assert src.steps() == [1, 2]
    assert src.body(2).bounds[5] == pytest.approx(2.0)
    assert src.flow(1, ["U"], None).n_cells == 32  # the other block is the flow
    assert VtkSource(tmp_path / "mb_*.vtm", body_block=1, flow_block="fluid").body(1).n_cells > 0
    with pytest.raises(KeyError, match="blocks are"):
        VtkSource(tmp_path / "mb_*.vtm", body_block="nope").body(1)
    with pytest.raises(ValueError, match="flow_block"):
        VtkSource(tmp_path / "mb_*.vtm").fields()


def test_no_body_and_no_series_raise_clearly(series):
    src = VtkSource(series / "wake_*.vtu")
    with pytest.raises(LookupError, match="no body"):
        src.body(10)
    with pytest.raises(KeyError, match="no time series"):
        src.series("lift")


def test_several_bodies_from_files(series):
    pv.Cube(center=(1, 1, 1)).save(series / "box.vtp")
    src = VtkSource(series / "wake_*.vtu", body={"ball": series / "body.vtp", "box": series / "box.vtp"})
    assert src.bodies() == ["ball", "box"]
    ball, box = src.body(10, "ball"), src.body(10, "box")
    assert src.body(10).n_cells == ball.n_cells + box.n_cells
    with pytest.raises(KeyError, match="ball, box"):
        src.body(10, "nope")


def test_several_bodies_from_blocks(tmp_path):
    pv.MultiBlock({"fluid": grid(1), "a": pv.Sphere(), "b": pv.Cube()}).save(tmp_path / "mb_1.vtm")
    src = VtkSource(tmp_path / "mb_*.vtm", body_block=["a", "b"])
    assert src.bodies() == ["a", "b"]
    assert src.body(1, "b").n_cells == 6
    assert src.flow(1, ["U"], None).n_cells == grid(1).n_cells     # the flow is the block left


def test_one_body_is_named_and_no_body_is_empty(series):
    assert VtkSource(series / "wake_*.vtu", body=series / "body.vtp").bodies() == ["body"]
    assert VtkSource(series / "wake_*.vtu").bodies() == []
