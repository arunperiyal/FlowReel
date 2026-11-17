"""Windowed PLT reading: a box of a long case read without loading the zone."""
import numpy as np
import pytest

from flowreel.box import Box
from flowreel.sources.flexflow import FlexflowSource
from flowreel.sources.flexflow import window as win
from flowreel.sources.flexflow.plt import PltFile
from flowreel.sources.flexflow.plt_write import write_plt

VARS = ["X", "Y", "Z", "U", "V", "W", "Pressure"]
NX, NY, NZ, LENGTH = 400, 3, 3, 100.0


def channel(shift: float = 0.0):
    """A channel 100 long and 3 x 3 across, of bricks; every node moved by ``shift`` in y.
    Its floor (y = -1.5) is a wall zone of quadrilaterals."""
    x = np.linspace(0, LENGTH, NX + 1)
    y = np.linspace(-1.5, 1.5, NY + 1)
    z = np.linspace(-1.5, 1.5, NZ + 1)
    zz, yy, xx = (a.ravel() for a in np.meshgrid(z, y, x, indexing="ij"))
    yy = yy + shift

    def node(i, j, k):
        return (k * (NY + 1) + j) * (NX + 1) + i

    bricks = np.array([[node(i, j, k), node(i + 1, j, k), node(i + 1, j + 1, k), node(i, j + 1, k),
                        node(i, j, k + 1), node(i + 1, j, k + 1), node(i + 1, j + 1, k + 1),
                        node(i, j + 1, k + 1)]
                       for k in range(NZ) for j in range(NY) for i in range(NX)])
    floor = np.array([[node(i, 0, k), node(i + 1, 0, k), node(i + 1, 0, k + 1), node(i, 0, k + 1)]
                      for k in range(NZ) for i in range(NX)])
    cols = [xx, yy, zz, xx, yy, zz, xx + yy]
    return cols, bricks, floor


@pytest.fixture
def case(tmp_path):
    for step, shift in ((1, 0.0), (2, 0.05)):
        cols, bricks, floor = channel(shift)
        write_plt(tmp_path / f"long.{step}.plt", VARS, cols,
                  [("fluid", 5, bricks), ("floor", 3, floor)], time=float(step))
    return tmp_path


BOX = Box((40.0, -2.0, -2.0), (50.0, 2.0, 2.0))


def test_the_window_holds_the_box_only(case):
    with PltFile(case / "long.1.plt") as plt:
        w = win.choose(plt, 0, BOX, chunk=1000)               # small chunks: chunking works
        npts = plt.zones[0]["npts"]
    assert len(w.cells) == 40 * NY * NZ                         # 40 of 400 cells along x
    assert len(w.nodes) == 41 * (NY + 1) * (NZ + 1) and len(w.nodes) < npts / 9
    assert w.cells.max() == len(w.nodes) - 1


def test_a_windowed_read_equals_a_whole_read(case):
    windowed = FlexflowSource(case).flow(2, ["U", "p"], BOX)
    whole = FlexflowSource(case, window=False).flow(2, ["U", "p"], BOX)
    assert windowed.n_cells == whole.n_cells == 40 * NY * NZ
    assert np.array_equal(windowed.points, whole.points)
    assert np.array_equal(windowed.cell_connectivity, whole.cell_connectivity)
    assert np.array_equal(windowed["p"], whole["p"]) and np.array_equal(windowed["U"], whole["U"])


def test_a_windowed_read_never_loads_a_whole_variable(case, monkeypatch):
    src = FlexflowSource(case)
    monkeypatch.setattr(PltFile, "read_variable", lambda *a, **k: pytest.fail("whole read"))
    small = PltFile.load_connectivity                           # a wall's own cells are fine

    def volume_never(self, zi, nen=None):
        assert self.zones[zi]["ztype"] not in (4, 5), "the volume's cells read whole"
        return small(self, zi, nen)
    monkeypatch.setattr(PltFile, "load_connectivity", volume_never)
    assert src.flow(1, ["U"], BOX).n_cells == 40 * NY * NZ
    assert src.body(1).n_cells == NX * NZ                       # the wall: its own nodes only


def test_the_window_is_chosen_once(case, monkeypatch):
    src = FlexflowSource(case)
    src.flow(1, ["U"], BOX)
    monkeypatch.setattr(win, "choose", lambda *a, **k: pytest.fail("chosen again"))
    src.flow(2, ["U"], BOX)                                         # the same box: kept


# -- margin and the cached index ---------------------------------------------------------

EDGE = Box((40.0, -1.48, -2.0), (50.0, 2.0, 2.0))    # the floor row is just outside at step 1


def test_a_margin_keeps_cells_the_motion_brings_in(case):
    # step 2 moves the mesh 0.05 up: the floor nodes (y = -1.5 at step 1) are inside
    whole = FlexflowSource(case, window=False).flow(2, ["U"], EDGE)
    tight = FlexflowSource(case, cache=None).flow(2, ["U"], EDGE)
    wide = FlexflowSource(case, margin=0.1, cache=None).flow(2, ["U"], EDGE)
    assert whole.n_cells == 40 * NY * NZ and tight.n_cells == 40 * (NY - 1) * NZ
    assert wide.n_cells == whole.n_cells and np.array_equal(wide.points, whole.points)
    with pytest.raises(ValueError, match="margin must be at least 0"):
        FlexflowSource(case, margin=-1)


def test_the_index_is_kept_on_disk_for_other_processes(case, tmp_path, monkeypatch):
    folder = tmp_path / "windows"
    FlexflowSource(case, cache=folder).flow(1, ["U"], BOX)
    assert len(list(folder.glob("*.npz"))) == 1
    real = win.build_span
    monkeypatch.setattr(win, "build_span", lambda *a, **k: pytest.fail("built again"))
    src = FlexflowSource(case, cache=folder)                         # a new process
    for x in range(0, 60, 5):                                        # a travelling window
        assert src.flow(1, ["U"], Box((x, -2, -2), (x + 10, 2, 2))).n_cells == 40 * NY * NZ
    import os
    os.utime(case / "long.1.plt", ns=(1, 1))                         # the file rewritten
    monkeypatch.setattr(win, "build_span", real)
    FlexflowSource(case, cache=folder).flow(1, ["U"], BOX)
    assert len(list(folder.glob("*.npz"))) == 2


def test_the_span_index_reads_only_the_box(case):
    with PltFile(case / "long.1.plt") as plt:
        span = win.build_span(plt, 0, chunk=500)
        assert span.axis == 0 and np.all(np.diff(span.lo) >= 0)
        assert len(span.candidates(BOX)) == 40 * NY * NZ + NY * NZ   # those starting inside
        fast = win.choose(plt, 0, BOX, span=span)
        scan = win.choose(plt, 0, BOX)
    assert np.array_equal(fast.nodes, scan.nodes) and np.array_equal(fast.cells, scan.cells)


def test_default_cache_and_none(case, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    FlexflowSource(case).flow(1, ["U"], BOX)
    assert len(list((tmp_path / "xdg" / "flowreel" / "windows").glob("*.npz"))) == 1
    FlexflowSource(case, cache=None).flow(1, ["U"], Box((0, -2, -2), (5, 2, 2)))
    assert len(list((tmp_path / "xdg" / "flowreel" / "windows").glob("*.npz"))) == 1
