"""The frame plan: for each frame of a shot, its step and the value of every track."""
from __future__ import annotations

from dataclasses import dataclass

from flowreel.scene.layers import Frame
from flowreel.scene.shot import Shot
from flowreel.scene.timing import ShotTime, parse_time


@dataclass
class FramePlan:
    """What a render does, frame by frame, before any data is read.

    ``shot`` is the parsed shot; ``time`` maps frames to saved steps; ``times`` holds each
    saved step's physical time. :meth:`frame` gives a :class:`~flowreel.scene.layers.Frame`
    whose ``values`` is a list with one dict per layer (every option at that frame), in
    the order of ``shot.layers``. The plan needs only the source's step list and times,
    so it is cheap and can be printed or hashed without loading a field.
    """

    shot: Shot
    time: ShotTime
    times: dict[int, float]

    @property
    def n_frames(self) -> int:
        """Number of frames in the shot."""
        return self.time.n_frames

    @property
    def frozen(self) -> bool:
        """True when every frame shows the same step."""
        return self.time.frozen

    def frame(self, index: int) -> Frame:
        """The plan for frame ``index`` (0-based): step, time and layer values."""
        step = self.time.step(index)
        return Frame(index=index, step=step, time=self.times[step],
                     values=[layer.values(index) for layer in self.shot.layers])

    def __iter__(self):
        for i in range(self.n_frames):
            yield self.frame(i)


def plan(shot: Shot, source) -> FramePlan:
    """Plan ``shot`` against ``source`` (anything with ``steps()`` and ``time(step)``).

    Raises :class:`~flowreel.scene.errors.ConfigError` when the shot's time does not fit
    the source's saved steps.
    """
    from flowreel.scene.errors import Checker
    saved = source.steps()
    time = parse_time(shot.time, saved, Checker(shot.file, ("time",)))
    times = {s: source.time(s) for s in set(time.steps())}
    return FramePlan(shot=shot, time=time, times=times)
