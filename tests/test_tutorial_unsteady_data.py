"""The second tutorial's data script (examples/tutorial_unsteady/get_data.py), on its
generated stand-in: the record's formats in, PLT files and a CSV series out."""
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).parent.parent / "examples" / "tutorial_unsteady" / "get_data.py"


@pytest.fixture(scope="module")
def gd():
    spec = importlib.util.spec_from_file_location("get_data_unsteady", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["get_data_unsteady"] = module
    spec.loader.exec_module(module)
    return module


def quiet(*_):
    pass


def test_the_stand_in_converts_to_plt_files_and_a_force_series(gd, tmp_path):
    from flowreel.sources.plt import PltSource
    out = gd.get(tmp_path, stand_in=True, say=quiet)
    src = PltSource(out)
    assert src.steps() == list(range(4000, 4161, 2))               # every second of 161
    assert src.time(4002) == pytest.approx(400.2)
    assert src.bodies() == ["cylinder"]
    flow = src.flow(4000, ["U", "V", "W", "p"], None)
    assert set(flow.celltypes) == {10}                               # tetrahedra
    assert (flow.compute_cell_sizes(length=False, area=False)["Volume"] > 0).all()
    assert flow.bounds[4:] == pytest.approx((-0.05, 0.05))
    wall = src.body(4000)
    assert wall.n_open_edges == 0                                    # closed: ends capped
    r = np.hypot(wall.points[:, 0], wall.points[:, 1])
    assert np.allclose(r, 0.5, atol=1e-6)
    force = (out / "force.csv").read_text().splitlines()
    assert force[0] == "time,fx,fy,mz"
    times = [float(line.split(",")[0]) for line in force[1:]]
    assert times[0] >= 400 - 1e-9 and times[-1] <= 416 + 1e-9
    assert "not the real data" in (out / "README.md").read_text()


def test_a_second_run_changes_nothing(gd, tmp_path):
    out = gd.get(tmp_path, stand_in=True, say=quiet)
    before = {p: p.stat().st_mtime_ns for p in (out / "binary").iterdir()}
    said = []
    gd.get(tmp_path, stand_in=True, say=said.append)
    assert any("nothing changed" in s for s in said)
    assert {p: p.stat().st_mtime_ns for p in (out / "binary").iterdir()} == before


def test_the_mesh_keeps_the_box_and_leaves_the_cylinder_out(gd):
    r = 0.5 * np.geomspace(1, 30, 12)
    th = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    R, T = np.meshgrid(r, th, indexing="ij")
    xy = np.c_[(R * np.cos(T)).ravel(), (R * np.sin(T)).ravel()]
    keep, tri, wall = gd.mesh(xy, box=(-3, 6, -2, 2))
    pts = xy[keep]
    assert (pts[:, 0] >= -3).all() and (pts[:, 0] <= 6).all() and (np.abs(pts[:, 1]) <= 2).all()
    centre = pts[tri].mean(axis=1)
    assert (np.hypot(*centre.T) > 0.5).all()
    assert len(wall) == 24 and np.allclose(np.hypot(*pts[wall].T), 0.5)


def test_the_prisms_cut_into_tetrahedra_that_meet_face_to_face(gd):
    tri = np.array([[0, 1, 2], [1, 3, 2]])                           # two triangles, one edge
    tets = gd.tetrahedra(tri, 4)
    faces = {}
    for t in tets:
        for f in ([t[0], t[1], t[2]], [t[0], t[1], t[3]], [t[0], t[2], t[3]], [t[1], t[2], t[3]]):
            key = tuple(sorted(f))
            faces[key] = faces.get(key, 0) + 1
    shared = [f for f, n in faces.items() if n == 2]
    assert len(tets) == 6
    assert all(n <= 2 for n in faces.values()) and len(shared) == 2 + 2 + 2  # in each prism, and the side between


def test_a_download_with_the_wrong_checksum_is_refused(gd, tmp_path):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    with pytest.raises(gd.ChecksumError, match="SHA-256"):
        gd.fetch("https://example.org/x", tmp_path / "x", "0" * 64,
                 lambda url, timeout: Response(b"not the record"), say=quiet)
    assert not list(tmp_path.iterdir())


def test_the_pinned_sums_are_sha256(gd):
    assert set(gd.FILES) == {"fixed_cylinder_atRe100", "Re100_fixe00.reactions"}
    assert all(len(s) == 64 for s in gd.FILES.values())
