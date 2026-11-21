import pytest

from flowreel.scene.camera_import import import_view
from flowreel.scene.errors import ConfigError


def prop(name, *values):
    elems = "".join(f'<Element index="{i}" value="{v}"/>' for i, v in enumerate(values))
    return f'<Property name="{name}" id="x.{name}" number_of_elements="{len(values)}">{elems}</Property>'


def render_view(pid, pos, focal, up=(0, 1, 0), angle=30, parallel=0, scale=1):
    return (f'<Proxy group="views" type="RenderView" id="{pid}" servers="21">'
            + prop("CameraPosition", *pos) + prop("CameraPositionInfo", 9, 9, 9)
            + prop("CameraFocalPoint", *focal) + prop("CameraViewUp", *up)
            + prop("CameraViewAngle", angle) + prop("CameraParallelProjection", parallel)
            + prop("CameraParallelScale", scale) + "</Proxy>")


def pvsm(tmp_path, *views):
    text = ('<?xml version="1.0"?>\n<ParaView><ServerManagerState version="5.11.0">'
            '<Proxy group="sources" type="Sphere" id="1"/>' + "".join(views)
            + "</ServerManagerState></ParaView>")
    path = tmp_path / "state.pvsm"
    path.write_text(text)
    return path


def test_pvsm_first_and_second_render_view(tmp_path):
    path = pvsm(tmp_path, render_view(10, (-19, 13, -5), (6, 0, 8.5), angle=40),
                render_view(20, (6, 40, 9.5), (6, 0, 9.5), up=(0, 0, -1), parallel=1, scale=10.6))
    v = import_view(path, "wide")
    assert (v.name, v.position, v.focal, v.up, v.view_angle, v.parallel) == (
        "wide", (-19, 13, -5), (6, 0, 8.5), (0, 1, 0), 40, False)
    top = import_view(path, "top", index=1)
    assert top.parallel and top.parallel_scale == 10.6 and top.up == (0, 0, -1)
    with pytest.raises(ConfigError, match="index 2 is out of range.*2 render views"):
        import_view(path, index=2)


def test_pvsm_without_a_camera(tmp_path):
    with pytest.raises(ConfigError, match="no render view camera"):
        import_view(pvsm(tmp_path))
    bad = tmp_path / "bad.pvsm"
    bad.write_text("<ParaView><unclosed>")
    with pytest.raises(ConfigError, match="not a ParaView state"):
        import_view(bad)


TRACE = """\
# trace generated using paraview version 5.11.0
from paraview.simple import *
renderView1 = GetActiveViewOrCreate('RenderView')
renderView1.CameraPosition = [-19.0, 13.0, -5.0]
renderView1.CameraFocalPoint = [6.0, 0.0, 8.5]
renderView1.CameraViewUp = [0.0, 1.0, 0.0]
renderView1.CameraParallelScale = 7.5
renderView1.CameraPosition = [-20.5, 13.0, -5.0]   # moved again: the last one wins
renderView2 = CreateView('RenderView')
renderView2.CameraPosition = [0, 50, 0]
renderView2.CameraFocalPoint = [0, 0, 0]
renderView2.CameraViewUp = [0, 0, -1]
renderView2.CameraParallelProjection = 1
renderView2.CameraParallelScale = 3.25e1
"""


def test_python_trace(tmp_path):
    path = tmp_path / "trace.py"
    path.write_text(TRACE)
    v = import_view(path, "main")
    assert v.position == (-20.5, 13, -5) and v.view_angle == 30 and not v.parallel
    assert v.parallel_scale == 1.0                     # unused by a perspective view
    top = import_view(path, "top", index=1)
    assert top.parallel and top.parallel_scale == 32.5 and top.up == (0, 0, -1)
    (tmp_path / "empty.py").write_text("print('no camera')\n")
    with pytest.raises(ConfigError, match="no render view camera"):
        import_view(tmp_path / "empty.py")


def test_flexflow_frame_and_cameras_yml(tmp_path):
    frame = tmp_path / "cam.yml"
    frame.write_text("# flexflow camera frame -- reuse with: field render ... --camera cam.yml\n"
                     "position: [1.0, 2.0, 10.0]\nfocal: [1.0, 2.0, 0.0]\nup: [0.0, 1.0, 0.0]\n"
                     "parallel: false\nparallel_scale: 4.0\nview_angle: 25.0\n")
    v = import_view(frame, "close")
    assert v.name == "close" and v.position == (1, 2, 10) and v.view_angle == 25
    many = tmp_path / "cameras.yml"
    many.write_text("views:\n  - {name: a, position: [0, 0, 1], focal: [0, 0, 0]}\n"
                    "  - {name: b, position: [0, 0, 2], focal: [0, 0, 0]}\n")
    assert import_view(many, "copy", view="b").position == (0, 0, 2)
    with pytest.raises(ConfigError, match="name the view to take: the file has a, b"):
        import_view(many)
    with pytest.raises(ConfigError, match="no view named 'c'"):
        import_view(many, view="c")


def test_unknown_kind_or_missing(tmp_path):
    with pytest.raises(ConfigError, match="kind of file"):
        import_view(tmp_path / "view.txt")
    with pytest.raises(ConfigError, match="no such file"):
        import_view(tmp_path / "gone.pvsm")
