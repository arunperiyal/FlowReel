"""render_frame and render: one frame in this process, many in a process each."""
import numpy as np
import pytest
from PIL import Image

from flowreel.scene import render, render_frame
from flowreel.scene.camera import shot_camera
from flowreel.scene.errors import ConfigError
from flowreel.scene.layers import FrameData
from flowreel.scene.shot import from_dict
from flowreel.scene.views import parse_view

VIEWS = {"main": parse_view({"name": "main", "position": [3, 2, 4], "focal": [0, 0, 0.5]}),
         "side": parse_view({"name": "side", "position": [4, 0, 0.5], "focal": [0, 0, 0.5]})}


def toy_shot(**extra):
    spec = {"name": "toy", "source": "toy:none", "time": {"steps": [0, 20]},
            "camera": {"view": "main"}, "size": [64, 48], "antialias": "none",
            "layers": [{"type": "body", "colour": "#ff0000"},
                       {"type": "outline", "bounds": "domain"}]}
    spec.update(extra)
    return from_dict(spec, file="toy.yml")


def picture(shot, source, frame=0, **kw):
    try:
        return render_frame(shot, frame, source, views=VIEWS, **kw)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")


def test_render_frame_draws_the_shot(toy_source):
    img = picture(toy_shot(), toy_source)
    assert img.shape == (48, 64, 3) and img.dtype == np.uint8
    red = (img[:, :, 0] > 100) & (img[:, :, 1] < 60)
    assert red.mean() > 0.01                                  # the body is there


def test_render_writes_every_frame_in_processes(toy_source, tmp_path):
    seen = []
    report = render(toy_shot(), source=toy_source, views=VIEWS, out=tmp_path, jobs=2,
                    progress=seen.append)
    assert [f.index for f in report.frames] == [0, 1, 2] and len(seen) == 3
    assert report.count("rendered") == 3 and report.folder == tmp_path / "toy"
    for f in report.frames:
        assert f.path.name == f"frame_{f.index:05d}.png" and f.peak_bytes > 0
    one = np.asarray(Image.open(report.frames[1].path))
    assert np.array_equal(one, picture(toy_shot(), toy_source, 1))
    assert not list((tmp_path / "toy").glob("*.part.png"))


def test_render_in_process_and_a_subset(toy_source, tmp_path):
    report = render(toy_shot(), [2, 0], source=toy_source, views=VIEWS, out=tmp_path,
                    processes=False)
    assert [f.index for f in report.frames] == [0, 2]
    assert sorted(p.name for p in (tmp_path / "toy").glob("*.png")) == \
        ["frame_00000.png", "frame_00002.png"]


def test_a_frame_outside_the_shot_is_an_error(toy_source, tmp_path):
    with pytest.raises(ConfigError, match="frame 3 is outside"):
        render(toy_shot(), [3], source=toy_source, views=VIEWS, out=tmp_path)
    with pytest.raises(ValueError, match="jobs"):
        render(toy_shot(), source=toy_source, views=VIEWS, out=tmp_path, jobs=0)


def test_lights_are_read_and_change_the_picture(toy_source):
    plain = picture(toy_shot(), toy_source)
    lit = picture(toy_shot(lights="raking"), toy_source)
    assert toy_shot(lights="raking").lights[0].kind == "scene"
    assert not np.array_equal(plain, lit)


def test_a_shot_file_opens_its_own_source(tmp_path):
    (tmp_path / "cameras.yml").write_text(
        "views:\n  - {name: main, position: [0, -30, 3], focal: [0, 0, 3], up: [0, 0, 1]}\n")
    (tmp_path / "s.yml").write_text(
        "name: g\nsource: geometry:grooved_cylinder\ntime: {frozen: 0}\n"
        "camera: {view: main}\nsize: [40, 30]\nantialias: none\nlayers: [{type: outline}]\n")
    try:
        img = render_frame(tmp_path / "s.yml", 0)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert img.shape == (30, 40, 3) and img.max() > 100


# --- camera -------------------------------------------------------------------------

def camera(spec, **kw):
    return shot_camera(toy_shot(camera=spec), VIEWS, kw.get("tracks"), rest_step=0)


def test_camera_track_fit_and_follow(toy_source):
    from flowreel.scene.camera_path import parse_track
    tracks = {"pan": parse_track({"keys": [{"frame": 0, "view": "main"},
                                            {"frame": 2, "view": "side"}]}, VIEWS)}
    data = FrameData(toy_source, 0)
    cam = camera({"track": "pan"}, tracks=tracks)
    assert cam.view(0, data).position == pytest.approx(VIEWS["main"].position)
    assert cam.view(2, data).position == pytest.approx(VIEWS["side"].position)
    fitted = camera({"fit": "domain", "direction_of": "side"}).view(0, data)
    assert fitted.focal == pytest.approx((0, 0, 0.5))
    assert fitted.direction == pytest.approx(VIEWS["side"].direction)
    station = float(toy_source.body(0).points[10, 2])     # on a ring of the sphere
    followed = camera({"view": "side", "follow": "sphere", "station": station}).view(0, data)
    assert followed.focal == pytest.approx((0, 0, station), abs=1e-6)


@pytest.mark.parametrize("spec, message", [
    ({}, "has no camera"),
    ({"view": "main", "track": "pan"}, "exactly one"),
    ({"view": "mian"}, "did you mean 'main'"),
    ({"fit": "domain"}, "needs 'direction_of'"),
    ({"view": "main", "margin": 2}, "only with 'fit'"),
    ({"view": "main", "follow": "sphere"}, "needs 'station'"),
    ({"view": "main", "station": 1}, "only with 'follow'"),
])
def test_camera_errors_name_the_key(spec, message):
    with pytest.raises(ConfigError, match=message) as err:
        camera(spec)
    assert "toy.yml: camera" in str(err.value)


def test_a_source_mapping_passes_options_and_resolves_paths(tmp_path, monkeypatch):
    from flowreel import sources
    from flowreel.scene.rendering import open_source
    seen = {}
    monkeypatch.setattr(sources, "create", lambda adapter, **kw: seen.update(adapter=adapter, **kw))
    shot = toy_shot(source={"adapter": "vtk", "path": "f_*.vti", "body": {"a": "a.vtp"}, "dt": 0.1})
    shot.file = str(tmp_path / "s.yml")
    assert shot.source == ("vtk", "f_*.vti") and shot.source_options["dt"] == 0.1
    open_source(shot)
    assert seen == {"adapter": "vtk", "path": str(tmp_path / "f_*.vti"),
                    "body": {"a": str(tmp_path / "a.vtp")}, "dt": 0.1}
    geo = toy_shot(source={"adapter": "geometry", "body": "grooved_cylinder"})
    open_source(geo)
    assert seen["body"] == "grooved_cylinder"                 # a name, not a file
    with pytest.raises(ConfigError, match="missing key 'adapter'"):
        toy_shot(source={"path": "x"})
