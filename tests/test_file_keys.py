"""A data file rewritten in place changes the keys of what it drew."""
import os

import numpy as np
import pyvista as pv

from flowreel import sources
from flowreel.project import PROJECT_FILE
from flowreel.scene.keys import file_stamps, frame_key
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import from_dict

from test_render import VIEWS


def write_case(folder):
    box = pv.ImageData(dimensions=(5, 5, 5), spacing=(0.5, 0.5, 0.25), origin=(-1, -1, 0))
    for name in ("U", "V", "W"):
        box.point_data[name] = np.zeros(box.n_points, np.float32)
    for step in (0, 1):
        box.save(folder / f"flow_{step}.vti")
    pv.Sphere(radius=0.2, center=(0, 0, 0.5)).save(folder / "body.vtp")


def shot(folder):
    spec = {"name": "k", "source": {"adapter": "vtk", "path": "flow_*.vti", "body": "body.vtp"},
            "time": {"steps": [0, 1]}, "camera": {"view": "main"}, "size": [32, 24],
            "layers": [{"type": "body"}]}
    return from_dict(spec, file=str(folder / "k.yml"))


def test_rewriting_a_file_changes_only_its_frames(tmp_path):
    write_case(tmp_path)
    keys = lambda: [frame_key(Scene.make(shot(tmp_path), views=VIEWS), i) for i in (0, 1)]  # noqa: E731
    before = keys()
    assert keys() == before                                       # nothing changed
    os.utime(tmp_path / "flow_1.vti", ns=(1, 10 ** 9))             # step 1 rewritten
    after = keys()
    assert after[0] == before[0] and after[1] != before[1]
    os.utime(tmp_path / "body.vtp", ns=(1, 2 * 10 ** 9))           # the body, used by both
    assert all(a != b for a, b in zip(keys(), after))


def test_stamps_of_each_source(tmp_path):
    write_case(tmp_path)
    src = sources.create("vtk", path=str(tmp_path / "flow_*.vti"), body=str(tmp_path / "body.vtp"))
    stamps = file_stamps(src, 1)
    assert [os.path.basename(s[0]) for s in stamps] == ["flow_1.vti", "body.vtp"]
    assert stamps[0][1] == (tmp_path / "flow_1.vti").stat().st_size
    assert file_stamps(sources.create("geometry", body="grooved_cylinder"), 0) == []
    assert file_stamps(object(), 0) is None                        # a source that does not say


def test_series_files_of_the_project_are_stamped(tmp_path):
    write_case(tmp_path)
    (tmp_path / "f.csv").write_text("time,fy\n0,1\n")
    for n in (0, 1):
        (tmp_path / f"d_{n}.csv").write_text("time,dy\n0,0\n")
    (tmp_path / PROJECT_FILE).write_text(
        "bodies: {ball: {zone: body, series: {force: f.csv, "
        "disp: {file: 'd_{node}.csv', by: node}}}}\n")
    scene = Scene.make(shot(tmp_path), views=VIEWS)
    names = [os.path.basename(s[0]) for s in file_stamps(scene.source, 0)]
    assert names == ["flow_0.vti", "body.vtp", "d_0.csv", "d_1.csv", "f.csv"]
