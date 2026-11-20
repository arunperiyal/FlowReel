"""The base clip of a layout shot: flow interpolated, rate: output panels laid on at the
film's rate, one drawn panel frame per output frame."""
import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.clips import Clips

from film_project import decode, film_file, frames, need_ffmpeg
from panel_project import project


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def board(folder):
    """A 160 x 90 layout: 3 flow frames on the left, a live lift plot on the right."""
    project(folder)
    frames(folder / "flow", 3, size=(80, 90))
    (folder / "lift.yml").write_text(yaml.safe_dump(
        {"type": "series", "size": [80, 90], "times": [0.0, 1.0, 2.0], "legend": False,
         "lines": [{"body": "bare", "series": "force", "column": "cl", "colour": "#ff0000"}]}))
    (folder / "board.yml").write_text(yaml.safe_dump({"size": [160, 90], "tiles": [
        {"frames": "flow", "at": [0, 0], "size": [80, 90]},
        {"panel": "lift.yml", "rate": "output", "at": [80, 0], "size": [80, 90]}]}))


def test_the_live_panel_is_laid_on_at_every_output_frame(tmp_path):
    board(tmp_path)
    f = film.load(film_file(tmp_path, [{"name": "c", "layout": "board.yml",
                                        "rate": {"fps": 8},
                                        "freezes": [{"at": 0.125, "hold": 0.25}]}]))
    c = Clips(f, panels={"processes": False})
    clip = c.base("c")
    n = round(c.line.shot("c").length * 24)                    # (3 + 2) frames x 3
    assert clip.frames == n == 15 and ff.frame_count(clip.path) == 15
    report = c.layout("c")
    (tile, drawn), = report.overlays
    assert drawn.count("drawn") == 15                           # one per output frame
    p = decode(clip.path).astype(int)
    for j in (0, 4, 9, 14):                                     # the panel, as drawn
        panel = np.asarray(Image.open(drawn.folder / f"frame_{j:05d}.png").convert("RGB"))
        assert np.abs(p[j][:, 80:] - panel).mean() < 6, j
    held = p[3:3 + 7, :, :80]                                   # flow frame 1, frozen
    assert np.abs(held - held[0]).max() < 6


def test_a_redrawn_panel_frame_rebuilds_the_clip(tmp_path):
    board(tmp_path)
    shots = [{"name": "c", "layout": "board.yml", "rate": {"fps": 8}}]
    first = Clips(film.load(film_file(tmp_path, shots)), panels={"processes": False}).base("c")
    again = Clips(film.load(tmp_path / "film.yml"), panels={"processes": False}).base("c")
    assert not again.built and again.key == first.key
    lift = yaml.safe_load((tmp_path / "lift.yml").read_text())
    lift["lines"][0]["colour"] = "#00ff00"
    (tmp_path / "lift.yml").write_text(yaml.safe_dump(lift))
    redrawn = Clips(film.load(tmp_path / "film.yml"), panels={"processes": False}).base("c")
    assert redrawn.built and redrawn.key != first.key
