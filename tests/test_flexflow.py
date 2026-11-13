"""The flexflow adapter, on a two-step piece cut from real solver output with
tools/cut_plt.py (half of the cylinder's boundary layer over one spanwise cell)."""
from pathlib import Path

import numpy as np
import pytest

from flowreel.box import Box
from flowreel.sources import Source
from flowreel.sources.flexflow import FlexflowSource
from flowreel.sources.flexflow.plt import PltFile

CASE = Path(__file__).parent / "data" / "flexflow_case"


@pytest.fixture
def src():
    return FlexflowSource(CASE)


def test_reader_header():
    with PltFile(CASE / "binary" / "riser.5000.plt") as plt:
        assert plt.vars[:7] == ["X", "Y", "Z", "U", "V", "W", "Pressure"]
        assert [z["name"] for z in plt.zones] == ["FIELD", "cyl"]
        assert plt.zones[0]["ztype"] == 5 and plt.zones[1]["ztype"] == 3
        assert plt.zones[0]["time"] == 250.0
        assert plt.shared_from(1) == [0]
        with pytest.raises(KeyError, match="FIELD"):
            plt.zone_index("nope")


def test_reader_loads_zones():
    with PltFile(CASE / "binary" / "riser.5000.plt") as plt:
        pts, conn, data, info = plt.load_zone(0)
        assert pts.shape == (4032, 3) and conn.shape == (1903, 8)
        assert not info["truncated"]
        assert np.array_equal(plt.read_variable(0, "U"), data["U"])
        lo, hi = plt.minmax(0)["Pressure"]
        assert lo == pytest.approx(data["Pressure"].min()) and hi == pytest.approx(data["Pressure"].max())
        body, bconn, bdata, binfo = plt.load_zone(1)   # shares the volume's arrays
        assert bconn.shape == (64, 4) and len(body) == binfo["npts"] < 4032
        assert np.array_equal(bdata["U"], data["U"][binfo["parent_nodes"]])


def test_is_a_source(src):
    assert isinstance(src, Source)
    assert src.steps() == [5000, 5005]
    assert src.time(5000) == 250.0 and src.time(5005) == 250.25


def test_fields_exclude_stored_derived(src):
    fields = src.fields()
    assert fields[:4] == ["U", "V", "W", "p"]
    assert not {"xVor", "yVor", "zVor", "QCriterion", "Pressure"} & set(fields)
    with pytest.raises(KeyError):
        src.flow(5000, ["QCriterion"], None)


def test_flow(src):
    g = src.flow(5000, ["U", "p"], None)
    assert g.n_cells == 1903 and g.n_points == 4032
    assert set(g.point_data.keys()) == {"U", "p"}
    assert (g.compute_cell_sizes()["Volume"] > 0).all()      # brick node order is VTK's
    assert Box.from_bounds(g.bounds).intersection(src.bounds()) is not None


def test_flow_crop_keeps_cells_inside(src):
    b = src.bounds()
    box = Box(b.lo, (b.hi[0], b.center[1], b.hi[2]))
    g = src.flow(5000, ["U"], box)
    assert 0 < g.n_cells < 1903
    assert box.expanded(1e-6).contains(g.points).all()


def test_body_is_on_the_wall_and_moves(src):
    b0, b1 = src.body(5000), src.body(5005)
    assert b0.n_cells == 64 and b0.n_points == b1.n_points
    # no slip: the wall's fluid velocity is the body's, one value per spanwise station
    for x in np.unique(np.round(b0.points[:, 0], 3)):
        station = np.isclose(b0.points[:, 0], x, atol=1e-3)
        for name in ("U", "V", "W"):
            assert np.ptp(b0.point_data[name][station]) < 1e-5
    # the wall is a circle of diameter 1 in y-z, displaced by dispY
    y = b0.points[:, 1] - b0.point_data["dispY"]
    assert np.allclose(np.hypot(y, b0.points[:, 2]), 0.5, atol=2e-3)
    assert b1.points[:, 1].mean() > b0.points[:, 1].mean()      # it moved in y


def test_bounds_and_memory(src):
    g = src.flow(5000, [], None)
    assert np.allclose(src.bounds().to_bounds(), g.bounds, atol=1e-5)
    assert 0 < src.memory_per_step(None) < 0.01


def test_missing_case_and_step(tmp_path, src):
    with pytest.raises(FileNotFoundError):
        FlexflowSource(tmp_path)
    with pytest.raises(KeyError, match="5000"):
        src.flow(1, ["U"], None)


def _write_series(case, name, folder, text):
    (case / folder).mkdir(parents=True, exist_ok=True)
    (case / folder / name).write_text(text)


def test_series(tmp_path):
    # Written here in the layout the prototype's extract_series.py reads.
    (tmp_path / "riser.1.plt").write_bytes((CASE / "binary" / "riser.5000.plt").read_bytes())
    _write_series(tmp_path, "a.othd", "othd_files",
                  "time 1.0\naleDisp 3 2\n0.0 0.1 0.2\n0.0 0.3 0.4\n"
                  "time 2.0\naleDisp 3 2\n0.0 0.5 0.6\n0.0 0.7 0.8\n")
    _write_series(tmp_path, "a.oisd", "oisd_files",
                  "time 1.0\ntotTrac 3 1\n1.0 2.0 3.0\nother 3 1\n9 9 9\n"
                  "time 2.0\ntotTrac 3 1\n4.0 5.0 6.0\n")
    src = FlexflowSource(tmp_path)
    d = src.series("displacement")
    assert list(d.columns) == ["time", "probe", "dx", "dy", "dz"]
    assert d[(d.time == 2.0) & (d.probe == 1)].dy.item() == 0.7
    f = src.series("force")
    assert list(f.columns) == ["time", "fx", "fy", "fz"]
    assert f.fy.tolist() == [2.0, 5.0]
    with pytest.raises(KeyError, match="displacement"):
        src.series("nope")


def test_series_restart_later_file_wins(tmp_path):
    import os
    (tmp_path / "riser.1.plt").write_bytes((CASE / "binary" / "riser.5000.plt").read_bytes())
    _write_series(tmp_path, "old.oisd", "oisd_files", "time 1.0\ntotTrac 3 1\n1 1 1\n")
    _write_series(tmp_path, "new.oisd", "oisd_files", "time 1.0\ntotTrac 3 1\n2 2 2\n")
    os.utime(tmp_path / "oisd_files" / "old.oisd", (1, 1))
    assert FlexflowSource(tmp_path).series("force").fx.tolist() == [2.0]


def test_zones_are_found_in_the_file(src):
    assert src.volume == "FIELD" and src.bodies() == ["cyl"]
    assert src.body(5000, "cyl").n_cells == src.body(5000).n_cells == 64
    with pytest.raises(KeyError, match="cyl"):
        src.body(5000, "wing")
    with pytest.raises(KeyError, match="FIELD"):
        FlexflowSource(CASE, body="wing")
    with pytest.raises(ValueError, match="not a volume zone"):
        FlexflowSource(CASE, volume="cyl")
