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


def scene_film(folder, scenes, **top):
    """Write ``film.yml`` in ``folder`` with ``scenes`` and a film size of :data:`SIZE`;
    returns its path."""
    data = {"fps": 24, "size": list(SIZE), "scenes": scenes, **top}
    path = folder / "film.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def shot_scenes(frames_folders, **rates):
    """A scene of one shot box over each frame folder name in ``frames_folders``; ``rates``
    gives a shot's options by folder name (``b={"rate": {...}}``)."""
    return [{"name": n, "layout": {"boxes": [{"shot": {"frames": n, **rates.get(n, {})}}]}}
            for n in frames_folders]


def decode(path) -> np.ndarray:
    """Every frame of a clip as ``(frames, height, width, 3)`` uint8 RGB."""
    w, h = (int(v) for v in ff.probe(path, "stream=width,height").split())
    done = subprocess.run([str(ff.find().ffmpeg), "-v", "error", "-i", str(path), "-f",
                           "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True)
    return np.frombuffer(done.stdout, np.uint8).reshape(-1, h, w, 3)


def mean_colour(frame) -> np.ndarray:
    return frame.reshape(-1, 3).mean(axis=0)
