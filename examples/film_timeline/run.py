"""Lay out a short film from its files and print its plan and captions.

Usage: python run.py [DIR]   (default ./film_timeline_example)

Needs no data: it makes DIR a project, writes generated frames into it (a wake of 120
frames at 24 frames a second, a comparison of 48 frames at 8), copies film.yml and
style.yml, and prints each scene's planned length (``film lengths``) and the captions
with their times (``film srt``). Nothing is drawn or built.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
from tag_project import flowreel  # noqa: E402
FRAMES = {"wake": 120, "compare": 48}


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    flowreel(folder, "project", "init", "--force")
    for name in ("film.yml", "style.yml"):
        shutil.copy(HERE / name, folder / name)
    for name, n in FRAMES.items():
        out = folder / "frames" / name
        out.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            Image.new("RGB", (64, 36), (i * 2 % 256, 40, 80)).save(out / f"frame_{i:05d}.png")
    print(flowreel(folder, "film", "lengths").strip())
    flowreel(folder, "film", "srt")
    print((folder / "film.srt").read_text().strip())


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_timeline_example"))
