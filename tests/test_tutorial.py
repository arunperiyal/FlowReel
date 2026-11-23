"""The tutorial (docs/tutorial/), followed command by command on the stand-in data at a
small size, and its pages checked against the files in examples/tutorial/project/."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
PAGES = ROOT / "docs" / "tutorial"
REFERENCE = ROOT / "examples" / "tutorial" / "project"
GET_DATA = ROOT / "examples" / "tutorial" / "get_data.py"
DATA = "data/cylinder_crossflow"
#: Small sizes for the test: the shots and panel, and the film.
SHOT_SIZE, FILM_SIZE = [320, 180], [640, 360]


def yaml_blocks(page: str) -> list:
    """Every ```yaml block of a tutorial page, loaded."""
    text = (PAGES / page).read_text()
    return [yaml.safe_load(b) for b in re.findall(r"```yaml\n(.*?)```", text, re.S)]


def reference(name: str):
    return yaml.safe_load((REFERENCE / name).read_text())


@pytest.mark.parametrize("page, name", [
    ("04-camera.md", "cameras.yml"),
    ("05-sweep.md", "shots/sweep.yml"),
    ("06-panel.md", "panels/pressure.yml"),
    ("07-film.md", "cards/title.yml"),
    ("07-film.md", "text/wake.yml"),
    ("07-film.md", "text/freeze.yml"),
    ("07-film.md", "film.yml"),
    ("02-project.md", "flowreel.yml"),
])
def test_the_pages_show_the_reference_files(page, name):
    assert reference(name) in yaml_blocks(page), f"{page} does not show {name} as it is"


def test_the_first_shot_is_the_reference_with_its_first_camera():
    wake = reference("shots/wake.yml")
    assert wake["camera"] == {"track": "approach"}
    assert {**wake, "camera": {"view": "main"}} in yaml_blocks("03-first-shot.md")
    assert {"camera": {"track": "approach"}} in yaml_blocks("04-camera.md")


def test_every_page_is_in_the_site_and_every_picture_exists():
    site = (ROOT / "mkdocs.yml").read_text()
    for page in sorted(PAGES.glob("*.md")):
        assert f"tutorial/{page.name}" in site, page.name
        for picture in re.findall(r"\]\((images/[^)]+)\)", page.read_text()):
            assert (PAGES / picture).is_file(), f"{page.name}: {picture}"


def small(path: Path, size) -> None:
    """Rewrite the ``size: [1920, 1080]`` of a file to ``size``."""
    text = path.read_text()
    assert "size: [1920, 1080]" in text, path
    path.write_text(text.replace("size: [1920, 1080]", f"size: {size}"))


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_following_the_tutorial_makes_a_20_second_film(tmp_path):
    from flowreel.film import ffmpeg
    try:
        ffmpeg.find()
    except Exception as exc:                                     # noqa: BLE001
        pytest.skip(f"no usable ffmpeg: {exc}")
    root = tmp_path / "cylinder"
    root.mkdir()
    env = {**os.environ, "NO_COLOR": "1"}

    def run(*args, script=None):
        command = [sys.executable, str(script), *args] if script else \
            [sys.executable, "-m", "flowreel", *args]
        done = subprocess.run(command, cwd=root, capture_output=True, text=True,
                              timeout=900, env=env)
        if done.returncode != 0 and ("OpenGL" in done.stderr or "EGL" in done.stderr):
            pytest.skip("off-screen rendering is not available")
        assert done.returncode == 0, f"{' '.join(args)}:\n{done.stdout[-1500:]}{done.stderr[-3000:]}"
        return done.stdout + done.stderr

    def take(name, size=None):                                   # write a file as the page says
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REFERENCE / name, target)
        if size:
            small(target, size)

    # 2. the project and the data
    assert "converted to" in run("--stand-in", script=GET_DATA)
    out = run("project", "init", f"vtk:{DATA}/flow.pvd", "--body", f"cylinder={DATA}/cylinder.vtp")
    assert "1 body (cylinder)" in out
    for folder in ("shots", "text", "cards", "assets"):
        assert (root / folder).is_dir()
    take("flowreel.yml")
    run("project", "info")

    # 3. a first shot, seen from the view project init wrote
    run("shot", "template", "wake", "--layers", "slice,body", "-o", "shots/wake.yml")
    take("shots/wake.yml", SHOT_SIZE)
    wake = root / "shots" / "wake.yml"
    wake.write_text(wake.read_text().replace("camera: {track: approach}", "camera: {view: main}"))
    run("shot", "preview", "shots/wake.yml")
    assert list(root.glob("frames/wake@*/frame_00119.png"))          # a quarter-size draft

    # 4. the camera: the track the editor writes
    take("cameras.yml")
    take("shots/wake.yml", SHOT_SIZE)
    run("shot", "preview", "shots/wake.yml", "--every", "24")

    # 5. a second shot, its range sweeping
    take("shots/sweep.yml", SHOT_SIZE)
    run("shot", "preview", "shots/sweep.yml", "--every", "12")

    # 6. the panel
    take("panels/pressure.yml", SHOT_SIZE)
    run("compose", "panel", "panels/pressure.yml")
    assert len(list((root / "frames" / "pressure").glob("frame_*.png"))) == 72

    # 7. the film file, the frames at the shots' size, film check
    for name in ("cards/title.yml", "text/wake.yml", "text/freeze.yml"):
        take(name)
    take("film.yml", FILM_SIZE)
    run("shot", "render", "shots/wake.yml", "-j", "4")
    run("shot", "render", "shots/sweep.yml", "-j", "4")
    out = run("film", "check")
    assert (root / "contact.png").is_file()
    assert "hidden" not in out                     # the pinned caption is on the picture

    # 8. the film
    out = run("film", "build", "--preview", "180")
    assert re.search(r"film\s+20\.00 s\s+20\.00 s\s+film\.mp4", out), out
    assert ffmpeg.length(root / "film.mp4") == pytest.approx(20.0, abs=0.05)
    assert (root / "film_180p.mp4").is_file()
    srt = (root / "film.srt").read_text()
    for words in ("Vorticity, from the velocity alone", "The cylinder, diameter 1",
                  "The same flow, its colours narrowed", "Pressure: high in front, low behind",
                  "Made with FlowReel"):
        assert words in srt, words
    out = run("project", "info")
    assert "film.yml: 5 shots, 20.0 s planned" in out
