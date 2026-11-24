"""A panning shot rendered, and a text and an arrow that follow the body in it.

Usage: python run.py [DIR]   (default ./anchored_caption_example)

Needs no data, only ffmpeg: vortex_case.py (examples/) makes DIR a project with a generated
vortex round a sphere as the tag ``vortex``. shots/pan.yml pans the camera round the
sphere with the flow frozen (24 frames). ``shot render`` records each frame's camera beside
the frames, which is what lets film.yml's text and arrow follow a point of the model: the
sphere's centre, and its top. The film is built into DIR/film.mp4, and stills of the scene
at three times show the text moving with the sphere (DIR/frames/scenes/pan/).
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import vortex_case  # noqa: E402
from tag_project import flowreel  # noqa: E402


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    vortex_case.make_project(folder)
    (folder / "shots").mkdir(exist_ok=True)
    shutil.copy(HERE / "shots" / "pan.yml", folder / "shots" / "pan.yml")
    shutil.copy(HERE / "cameras.yml", folder / "cameras.yml")
    shutil.copy(HERE / "film.yml", folder / "film.yml")
    rendered = flowreel(folder, "shot", "render", "shots/pan.yml", "-j", "2")
    print(re.search(r"(\d+) rendered, (\d+) skipped", rendered).group(0))
    flowreel(folder, "film", "build")
    print("built film.mp4")
    out = flowreel(folder, "scene", "preview", "pan", "--at", "0.3", "1.0", "1.7")
    print(re.sub(r" in [\d.]+ s", "", out.strip().splitlines()[-1]).replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("anchored_caption_example"))
