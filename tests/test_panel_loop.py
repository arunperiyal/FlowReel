"""The panel registry and the drawing loop: one figure, moved along in time."""
import numpy as np
import pytest
from PIL import Image

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict
from flowreel.scene.errors import ConfigError


@panels.register
class Bar(panels.PanelType):
    """A test panel: a white bar whose width is the time; counts its builds."""

    name = "test_bar"
    KEYS = ("colour",)
    builds = 0

    def parse(self, options, check):
        self.colour = options.get("colour", "white")

    def build(self, figure):
        type(self).builds += 1
        ax = figure.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_axis_off()
        (self.bar,) = ax.fill([0, 0, 0, 0], [0, 0, 1, 1], color=self.colour, antialiased=False, linewidth=0)

    def update(self, time):
        self.bar.set_xy([[0, 0], [time, 0], [time, 1], [0, 1]])


def bar(times=(0.25, 0.5, 1.0), **options):
    return from_dict({"type": "test_bar", "size": [40, 10], "times": list(times), **options},
                     file="bar.yml")


def white_width(path):
    p = np.asarray(Image.open(path).convert("L"))
    return int((p[5] > 128).sum())


def test_frames_are_drawn_at_their_times(tmp_path):
    Bar.builds = 0
    rep = panels.panel(bar(), tmp_path, processes=False)
    assert rep.folder == tmp_path / "bar" and rep.count("drawn") == 3
    assert [white_width(f[1]) for f in rep.frames] == [10, 20, 40]
    assert Image.open(rep.frames[0][1]).size == (40, 10)
    assert Bar.builds == 1                           # the figure is built once


def test_times_given_and_some_frames(tmp_path):
    rep = panels.panel(bar(), tmp_path, times=[0.75, 0.1], frames=[0], processes=False)
    assert [(f[0], white_width(f[1])) for f in rep.frames] == [(0, 30)]


def test_runs_of_consecutive_frames():
    work = list(range(10))
    assert panels._runs(work, 3) == [[0, 1, 2], [3, 4, 5, 6], [7, 8, 9]]
    assert panels._runs(work[:2], 8) == [[0], [1]]


def test_unknown_type_and_keys():
    with pytest.raises(ConfigError, match=r"bar\.yml: type: 'test_baz' is not allowed"):
        panels.make(from_dict({"type": "test_baz", "times": [0]}, file="bar.yml"))
    with pytest.raises(ConfigError, match=r"bar\.yml: color: unknown key .*'colour'"):
        panels.make(bar(color="red"))


def test_a_frame_outside_the_times(tmp_path):
    with pytest.raises(ConfigError, match=r"frame 3 is outside the panel's 0\.\.2"):
        panels.panel(bar(), tmp_path, frames=[3], processes=False)
