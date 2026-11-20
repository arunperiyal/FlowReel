"""Small generated films for clip tests: frame folders, a film file, decoded clips."""
import subprocess

import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel.film import ffmpeg as ff

SIZE = (160, 90)


def need_ffmpeg():
    """Skip when no usable ffmpeg is installed."""
    try:
        ff.find()
    except ff.FfmpegError as error:
        pytest.skip(str(error))


def colour(i: int) -> tuple[int, int, int]:
    """A distinct grey-free colour for frame ``i``."""
    return ((40 + 50 * i) % 256, (200 - 30 * i) % 256, (90 + 70 * i) % 256)


def frames(folder, n: int, size=SIZE, start=0):
    """``n`` frames, each one solid colour (:func:`colour`), named from ``start``."""
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", size, colour(start + i)).save(folder / f"frame_{i:05d}.png")
    return folder


def film_file(folder, shots, **top):
    """Write ``film.yml`` in ``folder`` with ``shots`` and a film size of :data:`SIZE`."""
    data = {"fps": 24, "size": list(SIZE), "shots": shots, **top}
    path = folder / "film.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def decode(path) -> np.ndarray:
    """Every frame of a clip as ``(frames, height, width, 3)`` uint8 RGB."""
    w, h = (int(v) for v in ff.probe(path, "stream=width,height").split())
    done = subprocess.run([str(ff.find().ffmpeg), "-v", "error", "-i", str(path), "-f",
                           "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(done.stdout, np.uint8).reshape(-1, h, w, 3)


def mean_colour(frame) -> np.ndarray:
    return frame.reshape(-1, 3).mean(axis=0)
