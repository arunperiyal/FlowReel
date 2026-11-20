"""Build the clips of a small film from generated frames.

Usage: python run.py [DIR]   (default ./film_clips_example)

Needs no data, only ffmpeg (conda install -n flexflow_env -c conda-forge ffmpeg). It
writes 24 frames of a generated wake into DIR, copies film.yml and card.yml, and builds
each shot's base and finished clip into DIR/clips/: an opening card, the wake at 8
frames a second interpolated to 24 with a freeze and captions, and its last frame held
under a closing line on black. Prints each clip's planned and measured frames. Run it
twice: the second run keeps every clip.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.clips import Clips

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


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("film.yml", "card.yml"):
        shutil.copy(HERE / name, folder / name)
    wake(folder / "frames" / "wake")
    clips = Clips(film.load(folder / "film.yml"))
    for s in clips.line.shots:
        clip = clips.finished(s.shot.name)
        measured = ff.frame_count(clip.path)
        print(f"{s.shot.name:8s} {s.length:5.2f} s  {clip.frames:3d} frames planned, "
              f"{measured:3d} measured, {'built' if clip.built else 'kept'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("film_clips_example"))
