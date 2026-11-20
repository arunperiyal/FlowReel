"""Lay out a short film from its files and print its timeline.

Usage: python run.py [DIR]   (default ./film_timeline_example)

Needs no data: it writes generated frames into DIR (a wake of 120 frames at 24 frames
a second, a comparison of 48 frames at 8), copies film.yml, style.yml and text/, and
prints when each shot starts, how long it lasts, its freezes and its captions' times.
Nothing is drawn: the film build comes in later branches.
"""
import shutil
import sys
from pathlib import Path

from PIL import Image

from flowreel import film

HERE = Path(__file__).parent
FRAMES = {"wake": 120, "compare": 48}


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("film.yml", "style.yml"):
        shutil.copy(HERE / name, folder / name)
    shutil.copytree(HERE / "text", folder / "text", dirs_exist_ok=True)
    for name, n in FRAMES.items():
        out = folder / "frames" / name
        out.mkdir(parents=True, exist_ok=True)
        for i in range(n):
            Image.new("RGB", (64, 36), (i * 2 % 256, 40, 80)).save(out / f"frame_{i:05d}.png")
    t = film.timeline(film.load(folder / "film.yml"))
    for s in t.shots:
        print(f"{s.shot.name:8s} {s.start:5.2f} s + {s.length:5.2f} s")
        for f in s.freezes:
            print(f"  freeze on frame {f.frame} at {f.start:g} s for {f.hold:g} s")
    for c in t.captions:
        print(f"  {c.start:5.2f} to {c.end:5.2f} s  {c.caption.lines[0]}")
    print(f"film {t.length:.2f} s")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_timeline_example"))
