"""Build a small film from generated frames and a generated tone.

Usage: python run.py [DIR]   (default ./film_build_example)

Needs no data, only ffmpeg (conda install -n flexflow_env -c conda-forge ffmpeg). It
writes 24 frames of a generated wake and a 440 Hz tone into DIR, copies film.yml and
card.yml, and builds DIR/film.mp4: an opening card, the wake with a freeze and
captions, its last frame held under a closing line, the tone underneath, three
chapters. It also writes film_180p.mp4 (a preview copy), film.srt, chapters.txt and
contact.png (a still at each caption). Prints the build's report, paths relative to
DIR. Run it twice: the second run keeps every clip and only joins again.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from flowreel.film import ffmpeg as ff
from flowreel.film.build import build
from flowreel.film.check import contact

HERE = Path(__file__).parent
N = 24


def wake(folder: Path) -> None:
    """Frames of a generated wake: rows of light and dark blobs drifting right. Written
    once: frames written again would be new frames, and their clips built again."""
    if (folder / f"frame_{N - 1:05d}.png").is_file():
        return
    folder.mkdir(parents=True, exist_ok=True)
    y, x = np.mgrid[0:360, 0:640].astype(float)
    for i in range(N):
        phase = (x - 160 - 12 * i) / 60
        w = np.sin(phase) * np.exp(-((y - 180 - 40 * np.cos(phase / 2)) / 50) ** 2) * (x > 160)
        rgb = np.stack([20 + 200 * w.clip(0), 30 + 60 * np.abs(w), 60 + 190 * (-w).clip(0)], -1)
        Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).save(folder / f"frame_{i:05d}.png")


def tone(path: Path) -> None:
    """Twenty seconds of a quiet 440 Hz tone, longer than the film: the build cuts it to
    the picture and fades it out at the end."""
    if not path.is_file():
        ff.run("-f", "lavfi", "-i", "sine=frequency=440:duration=20:sample_rate=48000", path)


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("film.yml", "card.yml"):
        shutil.copy(HERE / name, folder / name)
    wake(folder / "frames" / "wake")
    tone(folder / "tone.wav")
    built = build(folder / "film.yml", preview=180)
    sheet = contact(folder / "film.yml", at="caption", width=320)
    for line in built.table() + [f"contact {sheet}"]:
        print(line.replace(f"{folder}/", ""))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_build_example"))
