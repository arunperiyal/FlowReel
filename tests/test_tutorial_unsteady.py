"""The second tutorial (docs/tutorial/unsteady/), followed command by command on the
stand-in data, and its pages checked against examples/tutorial_unsteady/project/."""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent
PAGES = ROOT / "docs" / "tutorial" / "unsteady"
REFERENCE = ROOT / "examples" / "tutorial_unsteady" / "project"
GET_DATA = ROOT / "examples" / "tutorial_unsteady" / "get_data.py"
#: Small sizes for the test: the shot and the panel (the layout and film keep theirs,
#: since the captions are placed by pixels).
SHOT_SIZE, PANEL_SIZE = [320, 180], [160, 270]


def yaml_blocks(page: str) -> list:
    """Every ```yaml block of a page, loaded."""
    text = (PAGES / page).read_text()
    return [yaml.safe_load(b) for b in re.findall(r"```yaml\n(.*?)```", text, re.S)]


@pytest.mark.parametrize("page, name", [
    ("01-data.md", "flowreel.yml"),
    ("02-shot.md", "shots/wake.yml"),
    ("03-panel.md", "panels/force.yml"),
    ("03-panel.md", "layouts/board.yml"),
    ("04-film.md", "cards/title.yml"),
    ("04-film.md", "text/board.yml"),
    ("04-film.md", "text/freeze.yml"),
    ("04-film.md", "film.yml"),
])
def test_the_pages_show_the_reference_files(page, name):
    assert yaml.safe_load((REFERENCE / name).read_text()) in yaml_blocks(page), \
        f"{page} does not show {name} as it is"


def test_every_page_is_in_the_site_and_every_picture_exists():
    nav = (ROOT / "mkdocs.yml").read_text()
    for page in sorted(PAGES.glob("*.md")):
        assert f"tutorial/unsteady/{page.name}" in nav, page.name
        for picture in re.findall(r"\]\((images/[^)]+)\)", page.read_text()):
            assert (PAGES / picture).is_file(), (page.name, picture)


def small(path: Path, size) -> None:
    data = yaml.safe_load(path.read_text())
    data["size"] = list(size)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_following_the_tutorial_makes_a_17_second_film(tmp_path):
    from flowreel.film import ffmpeg
    try:
        ffmpeg.find()
    except Exception as exc:                                     # noqa: BLE001
        pytest.skip(f"no usable ffmpeg: {exc}")
    root = tmp_path / "shedding"
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

    def take(name, size=None):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REFERENCE / name, target)
        if size:
            small(target, size)

    # 1. the data and the project: plt:, and the force as a CSV series
    assert "converted" in run("--stand-in", script=GET_DATA)
    assert "1 body (cylinder)" in run("project", "init", "plt:data/cylinder_re100")
    take("flowreel.yml")
    assert "bodies:  cylinder" in run("project", "info")
    # 2. a shot that moves
    take("shots/wake.yml", SHOT_SIZE)
    assert "plt:../data/cylinder_re100" in run("project", "info")
    run("shot", "preview", "shots/wake.yml", "--every", "50")
    # 3. the force beside it
    take("panels/force.yml", PANEL_SIZE)
    run("compose", "panel", "panels/force.yml")
    assert len(list((root / "frames" / "force").glob("frame_*.png"))) == 221
    run("shot", "render", "shots/wake.yml", "-j", "4")
    take("layouts/board.yml")
    run("compose", "layout", "layouts/board.yml")
    assert len(list((root / "frames" / "board").glob("frame_*.png"))) == 221
    # 4. the film
    for name in ("cards/title.yml", "text/board.yml", "text/freeze.yml", "film.yml"):
        take(name)
    run("film", "check")
    assert (root / "contact.png").is_file()
    out = run("film", "build", "--preview", "180")
    film = [line for line in out.splitlines() if line.startswith("film ")][0]
    assert film.split()[1:3] == ["17.21", "s"] and film.split()[3:5] == ["17.21", "s"]
    srt = (root / "film.srt").read_text()
    assert "Slowed down to half the speed" in srt and "St = fD/U = 0.165" in srt
