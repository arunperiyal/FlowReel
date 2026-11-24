"""The first tutorial (docs/tutorials/steady/), followed command by command on the
stand-in data at a small size, and its pages checked against the files in
examples/tutorial/project/."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
PAGES = ROOT / "docs" / "tutorials" / "steady"
REFERENCE = ROOT / "examples" / "tutorial" / "project"
GET_DATA = ROOT / "examples" / "tutorial" / "get_data.py"
DATA = "data/cylinder_crossflow"
#: Small sizes for the test: the panel drawn alone, and the film (the shots are drawn at
#: the size of their boxes in it).
PANEL_SIZE, FILM_SIZE = [480, 135], [640, 360]


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
    ("08-layout.md", "layouts/compare.yml"),
    ("08-layout.md", "layouts/title.yml"),
    ("09-film.md", "film.yml"),
])
def test_the_pages_show_the_reference_files(page, name):
    assert reference(name) in yaml_blocks(page), f"{page} does not show {name} as it is"


def test_the_tags_edits_are_the_reference_domain():
    domain = reference("data/crossflow/domain.yml")
    edits = {"units": domain["units"], "bodies": domain["bodies"]}
    assert edits in yaml_blocks("02-project.md")


def test_the_first_shot_is_the_reference_with_its_first_camera():
    wake = reference("shots/wake.yml")
    assert wake["camera"] == {"track": "approach"}
    assert {**wake, "camera": {"view": "main"}} in yaml_blocks("03-first-shot.md")
    assert {"camera": {"track": "approach"}} in yaml_blocks("04-camera.md")


def test_the_film_grows_scene_by_scene():
    film = reference("film.yml")
    scenes = {s["name"]: s for s in film["scenes"]}
    first = {k: v for k, v in film.items() if k != "scenes"}
    assert {**first, "scenes": [scenes["wake"]]} in yaml_blocks("07-scene.md")
    blocks = yaml_blocks("08-layout.md")
    assert [scenes["compare"]] in blocks and [scenes["title"]] in blocks


def test_every_page_is_in_the_site_and_every_picture_exists():
    site = (ROOT / "mkdocs.yml").read_text()
    for page in sorted(PAGES.glob("*.md")):
        assert f"tutorials/steady/{page.name}" in site, page.name
        for picture in re.findall(r"\]\((images/[^)]+)\)", page.read_text()):
            assert (PAGES / picture).is_file(), f"{page.name}: {picture}"


def small(path: Path, size) -> None:
    """Rewrite the full ``size`` of a file (``[1920, 1080]``, or a panel's ``[1920, 540]``)
    to ``size``."""
    text = path.read_text()
    full = next(s for s in ("size: [1920, 1080]", "size: [1920, 540]") if s in text)
    path.write_text(text.replace(full, f"size: {size}", 1))


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell")
def test_following_the_tutorial_makes_a_20_second_film(tmp_path):
    from flowreel.film import ffmpeg
    try:
        ffmpeg.find()
    except Exception as exc:                                     # noqa: BLE001
        pytest.skip(f"no usable ffmpeg: {exc}")
    root = tmp_path / "films"                                   # where the reader starts
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

    # 2. the project and its data: the case outside the project, brought in as a tag
    assert "converted to" in run("--stand-in", script=GET_DATA)
    run("project", "init", "-o", "cylinder")
    root = root / "cylinder"
    out = run("data", "import", "vtk", "--path", "../cases/cylinder_crossflow", "--tag",
              "crossflow", "--body", "cylinder=../cases/cylinder_crossflow/cylinder.vtp")
    assert "data/crossflow/domain.yml" in out
    domain = root / "data" / "crossflow" / "domain.yml"
    text, edits = domain.read_text(), (REFERENCE / "data/crossflow/domain.yml").read_text()
    domain.write_text(text[:text.index("units:")] + edits[edits.index("units:"):]
                      + text[text.index("measured:"):])           # as the page says
    assert "crossflow: ok" in run("data", "check")
    assert "tags:    crossflow (vtk, 1 steps)" in run("project", "info")

    # 3. a first shot, seen from the view project init wrote
    run("shot", "template", "wake", "--layers", "slice,body", "-o", "shots/wake.yml")
    take("shots/wake.yml")
    wake = root / "shots" / "wake.yml"
    wake.write_text(wake.read_text().replace("camera: {track: approach}", "camera: {view: main}"))
    run("shot", "preview", "shots/wake.yml")
    assert list(root.glob("frames/wake@*/frame_00119.png"))          # a quarter-size draft

    # 4. the camera: the track the editor writes
    take("cameras.yml")
    take("shots/wake.yml")
    run("shot", "preview", "shots/wake.yml", "--every", "24")

    # 5. a second shot, its range sweeping
    take("shots/sweep.yml")
    run("shot", "preview", "shots/sweep.yml", "--every", "12")

    # 6. the panel
    take("panels/pressure.yml", PANEL_SIZE)
    run("panel", "draw", "panels/pressure.yml")
    assert len(list((root / "frames" / "pressure").glob("frame_*.png"))) == 72

    # 7. a scene of one box: the film file with the wake alone, the shot at its box's size
    film = yaml.safe_load((REFERENCE / "film.yml").read_text())
    film["scenes"] = [s for s in film["scenes"] if s["name"] == "wake"]
    film["size"] = FILM_SIZE
    (root / "film.yml").write_text(yaml.safe_dump(film, sort_keys=False))
    run("shot", "render", "shots/wake.yml", "-j", "4")
    from PIL import Image
    assert Image.open(root / "frames" / "wake" / "frame_00000.png").size == tuple(FILM_SIZE)
    assert re.search(r"wake\s+0\.00 s\s+7\.00 s", run("scene", "list"))
    run("scene", "preview", "wake", "--at", "2", "5.5")
    assert (root / "frames" / "scenes" / "wake" / "at_5.50.png").is_file()

    # 8. a layout of several boxes, and a title
    take("layouts/compare.yml")
    take("layouts/title.yml")
    take("film.yml", FILM_SIZE)
    run("shot", "render", "shots/sweep.yml", "-j", "4")
    assert Image.open(root / "frames" / "sweep" / "frame_00000.png").size == (FILM_SIZE[0], FILM_SIZE[1] // 2)
    run("scene", "preview", "compare", "--at", "1", "4.5")
    run("scene", "preview", "title", "--at", "2")

    # 9. the film: checked, built, with a preview
    run("film", "check")
    assert (root / "contact.png").is_file()
    out = run("film", "build", "--preview", "180")
    assert re.search(r"film\s+20\.00 s\s+20\.00 s\s+film\.mp4", out), out
    assert re.search(r"wake\s+7\.00 s\s+7\.00 s\s+kept", out), out     # made by film check
    assert ffmpeg.length(root / "film.mp4") == pytest.approx(20.0, abs=0.05)
    assert (root / "film_180p.mp4").is_file()
    srt = (root / "film.srt").read_text()
    for words in ("Vorticity, from the velocity alone", "The cylinder, diameter 1",
                  "The same flow, its colours narrowed", "Pressure: high in front, low behind",
                  "Made with FlowReel"):
        assert words in srt, words
    assert (root / "chapters.txt").read_text().startswith("0:00 Opening")
    out = run("project", "info")
    assert "film.yml: 4 scenes" in out and "layouts: compare, title" in out
