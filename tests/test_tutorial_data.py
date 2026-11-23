"""examples/tutorial/get_data.py: checksums, the stand-in, its conversion, and reruns."""
import importlib.util
import io
from pathlib import Path

import numpy as np
import pytest
import pyvista as pv

SCRIPT = Path(__file__).parent.parent / "examples" / "tutorial" / "get_data.py"


@pytest.fixture(scope="module")
def gd():
    spec = importlib.util.spec_from_file_location("get_data", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def opener_for(files: dict[str, bytes], calls: list):
    """A stand-in for ``urlopen`` serving ``files`` by the last part of the URL."""
    def opener(url, timeout=None):
        calls.append(url)
        return io.BytesIO(files[url.rsplit("/", 1)[-1]])
    return opener


def quiet(*_):
    pass


def test_a_file_with_the_wrong_checksum_is_refused_and_not_kept(gd, tmp_path):
    calls = []
    target = tmp_path / "x.geo"
    with pytest.raises(gd.ChecksumError, match="SHA-256"):
        gd.fetch("https://example.org/x.geo", target, "0" * 64, opener_for({"x.geo": b"x"}, calls))
    assert not target.exists() and not list(tmp_path.iterdir())


def test_a_file_already_there_is_not_downloaded_again(gd, tmp_path):
    target = tmp_path / "x.geo"
    target.write_bytes(b"data")
    calls = []
    assert not gd.fetch("https://example.org/x.geo", target, gd.sha256(target),
                        opener_for({}, calls))
    assert calls == []


def faces_point_out(grid):
    """Whether every face of every cell, in VTK's face order, points away from the cell.

    Checked from the points rather than with ``compute_cell_sizes``: the sign VTK gives a
    wedge's volume flipped in VTK 9.7, while its faces (what is drawn) did not."""
    centres = grid.cell_centers().points
    for i in range(grid.n_cells):
        for face in grid.get_cell(i).faces:
            p = face.points
            if np.dot(np.cross(p[1] - p[0], p[2] - p[0]), p.mean(axis=0) - centres[i]) <= 0:
                return False
    return True


def test_the_stand_in_converts_to_the_names_and_fields_of_the_real_data(gd, tmp_path):
    out = gd.get(tmp_path, stand_in=True, say=quiet)
    assert out == tmp_path / "data" / "cylinder_crossflow"
    for name in ("flow.pvd", "flow_0.vtu", "cylinder.vtp", "LICENSE", "README.md",
                 "ensight/cylinder_Re35.case"):
        assert (out / name).is_file(), name
    flow = pv.read(out / "flow_0.vtu")
    assert set(np.unique(flow.celltypes)) == {gd.WEDGE, gd.HEXAHEDRON}
    assert sorted(flow.point_data) == ["U", "V", "W", "p"]      # vorticity_mag left out
    assert flow.bounds[4:] == pytest.approx((-0.05, 0.05))      # 0.1 diameter of span
    assert faces_point_out(flow)                                 # no cell turned inside out
    body = pv.read(out / "cylinder.vtp")
    assert body.bounds[1] - body.bounds[0] == pytest.approx(1.0, abs=1e-3)
    assert body.n_open_edges == 0                                # capped: seen end-on, solid
    faces = body.compute_normals(cell_normals=True, point_normals=False, split_vertices=False,
                                 auto_orient_normals=False, consistent_normals=False)
    out_of_axis = faces.cell_centers().points - (2.5, 0, 0)
    out_of_axis[np.abs(out_of_axis[:, 2]) < 0.049, 2] = 0         # the band: radially out
    assert ((out_of_axis * faces["Normals"]).sum(1) > 0).all()  # every face faces outwards
    assert "stand-in, not the real data" in (out / "README.md").read_text()


def test_flowreel_reads_the_converted_stand_in(gd, tmp_path):
    from flowreel.sources.vtk import VtkSource
    out = gd.get(tmp_path, stand_in=True, say=quiet)
    source = VtkSource(out / "flow.pvd", body={"cylinder": out / "cylinder.vtp"})
    assert source.steps() == [0]
    assert {"U", "V", "W", "p"} <= set(source.fields())
    assert source.bodies() == ["cylinder"]
    flow = source.flow(0, ["U", "p"], None)
    # potential flow: twice the free stream at the top of the cylinder, none in front
    top = flow.find_closest_point((2.5, 0.5, 0.0))
    assert flow.point_data["U"][top] == pytest.approx(70.0, rel=0.02)


def test_a_second_run_changes_nothing(gd, tmp_path):
    lines = []
    out = gd.get(tmp_path, stand_in=True, say=lines.append)
    before = {p: p.stat().st_mtime_ns for p in out.rglob("*") if p.is_file()}
    lines.clear()
    gd.get(tmp_path, stand_in=True, say=lines.append)
    assert any("nothing changed" in line for line in lines)
    assert {p: p.stat().st_mtime_ns for p in out.rglob("*") if p.is_file()} == before


def test_download_then_rerun_downloads_nothing(gd, tmp_path, monkeypatch):
    # serve the stand-in's files as if they were the published ones
    published = gd.write_stand_in(tmp_path / "published").parent
    licence = b"Apache License, Version 2.0 (stand-in for the test)\n"
    files = {name: (published / name).read_bytes() for name in gd.FILES}
    files["LICENSE"] = licence
    monkeypatch.setattr(gd, "FILES", {name: gd.sha256(published / name) for name in gd.FILES})
    monkeypatch.setattr(gd, "LICENSE_SHA256", __import__("hashlib").sha256(licence).hexdigest())
    calls = []
    out = gd.get(tmp_path / "project", opener=opener_for(files, calls), say=quiet)
    assert len(calls) == 6 and all(c.startswith(gd.BASE) for c in calls)
    assert (out / "LICENSE").read_bytes() == licence
    assert "Matthew Flamm" in (out / "README.md").read_text()
    calls.clear()
    lines = []
    gd.get(tmp_path / "project", opener=opener_for(files, calls), say=lines.append)
    assert calls == [] and any("nothing changed" in line for line in lines)


def test_the_stand_in_is_not_mistaken_for_the_real_data(gd, tmp_path):
    gd.get(tmp_path, stand_in=True, say=quiet)
    with pytest.raises(RuntimeError, match="holds the stand-in"):
        gd.get(tmp_path, opener=opener_for({}, []), say=quiet)


def test_the_published_checksums_are_pinned(gd):
    assert gd.COMMIT in gd.BASE
    assert set(gd.FILES) == {f"cylinder_Re35.{e}" for e in ("case", "geo", "scl1", "scl2", "vel")}
    assert all(len(h) == 64 for h in [*gd.FILES.values(), gd.LICENSE_SHA256])
