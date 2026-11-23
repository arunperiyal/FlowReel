"""flowreel camera: edit, path, orbit, import, project, preview."""
import pytest

from flowreel.scene.camera_path import load_tracks
from flowreel.scene.views import View, load_views

from cli_harness import Shell

SHOT = """name: g
source: geometry:grooved_cylinder
time: {frozen: 0, frames: 6}
camera: {view: main}
size: [64, 48]
antialias: none
layers:
  - {type: outline, width: 2}
  - {type: geometry, body: grooved_cylinder, colour: "#ff0000"}
"""
CAMERAS = ("views:\n  - {name: main, position: [0, -30, 3], focal: [0, 0, 3], up: [0, 0, 1]}\n"
           "  - {name: top, position: [0, 0, 40], focal: [0, 0, 3], up: [0, 1, 0]}\n")


@pytest.fixture
def sh(tmp_path, monkeypatch):
    (tmp_path / "g.yml").write_text(SHOT)
    (tmp_path / "cameras.yml").write_text(CAMERAS)
    (tmp_path / "flowreel.yml").write_text("")              # a project (docs/guide/projects/project.md)
    monkeypatch.chdir(tmp_path)
    return Shell(tmp_path / "store")


def ok(sh, line):
    status, out, err = sh.run(line)
    if status and ("OpenGL" in err or "EGL" in err):
        pytest.skip("off-screen rendering is not available")
    assert status == 0, err
    return out


def fails(sh, line):
    status, out, err = sh.run(line)
    assert status != 0, out
    return err


def cameras(tmp_path, name="cameras.yml"):
    views = load_views(tmp_path / name)
    return views, load_tracks(tmp_path / name, views)


def test_path_writes_a_track_with_segment_eases(sh, tmp_path):
    out = ok(sh, "camera path intro --keys 0:main:hold 24:main 72:top --path spline --frames 80")
    assert "wrote track 'intro' (3 keys, frames 0 to 72)" in out
    t = cameras(tmp_path)[1]["intro"]
    assert t.path == "spline" and t.frames == 80 and t.eases == (("hold", None, None))
    assert "no view named 'side'" in fails(sh, "camera path x --keys 0:main 9:side")
    assert "frames must increase" in fails(sh, "camera path x --keys 9:main 0:top")
    assert "FRAME:VIEW" in fails(sh, "camera path x --keys main")
    assert "unknown ease" in fails(sh, "camera path x --keys 0:main --ease fast")


def test_orbit_round_a_point_and_a_body(sh, tmp_path):
    out = ok(sh, "camera orbit turn --target 0 0 3 --radius 20 --frames 120 --span 90 "
                 "--elevation 10 30 --axis z")
    assert "wrote track 'turn': 19 views round (0, 0, 3) over 120 frames" in out
    views, tracks = cameras(tmp_path)
    assert "main" in views and tracks["turn"].frames == 120
    ok(sh, "camera orbit groove --shot g.yml --station 2 --radius 5 --frames 24 --span 30 "
           "--up 0 1 0")
    views = cameras(tmp_path)[0]
    assert views["groove_00"].focal == pytest.approx((2, 0, 0), abs=1e-3)  # along x, station 2
    assert views["groove_00"].position == pytest.approx((2, 0, 5), abs=1e-3)   # azimuth 0: +z
    assert "parallel" in fails(sh, "camera orbit g2 --shot g.yml --station 2 --radius 5 "
                                   "--frames 24 --up 0 0 1")
    assert "give --target" in fails(sh, "camera orbit x --radius 1 --frames 9")
    assert "needs --shot" in fails(sh, "camera orbit x --station 2 --radius 1 --frames 9")
    assert "radius" in fails(sh, "camera orbit x --target 0 0 0 --radius 0 --frames 9")
    assert "--elevation" in fails(sh, "camera orbit x --target 0 0 0 --radius 1 --frames 9 "
                                      "--elevation 1 2 3")


def test_import_a_paraview_trace(sh, tmp_path):
    (tmp_path / "trace.py").write_text(
        "v = GetActiveViewOrCreate('RenderView')\nv.CameraPosition = [1, 2, 30]\n"
        "v.CameraFocalPoint = [1, 2, 3]\nv.CameraViewUp = [0, 1, 0]\nv.CameraViewAngle = 25\n")
    out = ok(sh, "camera import trace.py wide")
    assert "wrote view 'wide' (view angle 25) from trace.py" in out
    assert cameras(tmp_path)[0]["wide"].position == (1, 2, 30)
    assert "already" in fails(sh, "camera import trace.py wide")
    ok(sh, "camera import trace.py wide --force")
    assert "kind of file" in fails(sh, "camera import trace.txt x")


def test_project_a_view_and_a_track(sh, tmp_path):
    out = ok(sh, "camera project --view main --points 0,0,3 0,-40,3 --size 200 100")
    lines = out.splitlines()
    assert lines[0].split() == ["0,0,3", "0,-40,3"]
    assert lines[1].split()[:2] == ["(100.0,", "50.0)"] and "behind" in lines[1]
    sh.run("use view:top")
    assert "(100.0, 50.0)" in ok(sh, "camera project --points 0,0,3 --size 200 100")
    ok(sh, "camera path t --keys 0:main 10:top")
    out = ok(sh, "camera project --track t --points 0,0,3 --frames 0:10:5 --size 200 100")
    assert [line.split()[0] for line in out.splitlines()] == ["frame", "0", "5", "10"]
    assert "no track 'u'" in fails(sh, "camera project --track u --points 0,0,0")
    assert "not x,y,z" in fails(sh, "camera project --view main --points 1,2")


def test_preview_draws_small_frames(sh, tmp_path):
    ok(sh, "camera path t --keys 0:main 10:top --frames 11")
    out = ok(sh, "camera preview t g.yml --every 5 --scale 0.5")
    assert "3 frames of 't' at 32x24" in out
    names = sorted(p.name for p in (tmp_path / "frames" / "t@preview").glob("*.png"))
    assert names == ["frame_00000.png", "frame_00005.png", "frame_00010.png"]


def test_edit_picks_a_track(sh, tmp_path, monkeypatch):
    import flowreel.cli.camera as cli
    import flowreel.editor.window as win

    class Scripted(win.EditorWindow):
        def __init__(self, state, scenes, size=(1280, 720), anchors=()):
            super().__init__(state, scenes, size=(160, 90), off_screen=True, anchors=anchors)

        def show(self):
            self.press("s")
            self.set_frame(5)
            self.look(View((0, -20, 10), (0, 0, 3), (0, 0, 1)))
            self.press("s")
            self.plotter.close()

    monkeypatch.setattr(win, "EditorWindow", Scripted)
    monkeypatch.setattr(cli, "_display", lambda: True)
    out = ok(sh, "camera edit g.yml --track picked")
    assert "track picked: 2 views saved" in out
    t = cameras(tmp_path)[1]["picked"]
    assert [k[0] for k in t.keys] == [0, 5] and t.frames == 6


def test_edit_away_from_the_data_and_errors(sh, tmp_path, monkeypatch):
    import flowreel.cli.camera as cli
    monkeypatch.setattr(cli, "_display", lambda: False)
    assert "no display" in fails(sh, "camera edit g.yml --track t")
    assert "give a shot" in fails(sh, "camera edit --track t")
    ok(sh, "shot render g.yml --save-vtp vtp")
    assert "--frames N is needed" in fails(sh, "camera edit --vtp vtp --track t")
    assert "give -c FILE" in fails(sh, "camera edit --vtp vtp --track t --frames 9")
    assert "no display" in fails(sh, "camera edit --vtp vtp --track t --frames 9 -c c.yml")


@pytest.mark.parametrize("action", ["edit", "path", "orbit", "import", "project", "preview"])
def test_every_action_has_help_with_examples(action, capsys):
    from flowreel.cli import main
    assert main(["camera", action, "--help"]) == 0
    text = capsys.readouterr().out
    assert f"flowreel camera {action}" in text and "examples:" in text
