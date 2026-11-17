"""The time of a shot: which simulation step each frame shows (plan Section 7.1).

Three forms, all under the shot's ``time`` key::

    time: {steps: [5000, 5600], every: 5}      # saved steps in a range, every 5th, one per frame
    time: {frozen: 5000, frames: 120}          # one step held for 120 frames
    time: {keys: [[0, 5000], [120, 5300]]}     # a time track: frame -> step, eased

Fields are never interpolated: a frame always shows a saved step (the nearer one when a
track lands between two).
"""
from __future__ import annotations

from flowreel.scene.errors import Checker, ConfigError
from flowreel.tracks import TimeTrack, nearest_step

FORMS = ("steps", "frozen", "keys")
KEYS = ("steps", "every", "frozen", "frames", "keys", "ease")


class ShotTime:
    """Maps the frames of a shot to saved steps.

    Build with :func:`parse_time`. ``n_frames`` is the frame count; ``step(frame)`` the
    saved step shown at that frame (0-based); ``frozen`` is true when every frame shows
    the same step, which lets the renderer contour once (Section 7.5).
    """

    def __init__(self, steps: list[int]):
        if not steps:
            raise ValueError("a shot needs at least one frame")
        self._steps = list(steps)

    @property
    def n_frames(self) -> int:
        """Number of frames."""
        return len(self._steps)

    @property
    def frozen(self) -> bool:
        """True when all frames show one step."""
        return len(set(self._steps)) == 1

    def step(self, frame: int) -> int:
        """The saved step shown at ``frame``."""
        if not 0 <= frame < len(self._steps):
            raise IndexError(f"frame {frame} is outside 0..{len(self._steps) - 1}")
        return self._steps[frame]

    def steps(self) -> list[int]:
        """The step of every frame, in order."""
        return list(self._steps)


def parse_time(spec: dict, saved: list[int], check: Checker | None = None) -> ShotTime:
    """Resolve the shot's ``time`` mapping against the source's ``saved`` step numbers.

    ``steps``: the saved steps from ``steps[0]`` to ``steps[1]`` inclusive, keeping
    every ``every``-th one (default 1); one frame each.
    ``frozen``: the saved step nearest to it, held for ``frames`` frames (default 1).
    ``keys``: a time track (``ease`` default ``linear``); with ``frames`` the shot has
    that many frames, otherwise one more than the last key's frame.
    Exactly one of the three forms must be given. Raises
    :class:`~flowreel.scene.errors.ConfigError` otherwise or when no saved step fits.
    """
    check = check or Checker(None, ("time",))
    spec = check.mapping(spec, KEYS)
    given = [f for f in FORMS if f in spec]
    if len(given) != 1:
        raise check.error(f"give exactly one of {', '.join(FORMS)}"
                          + (f", got {', '.join(given)}" if given else ""))
    if not saved:
        raise check.error("the source has no saved steps")
    form = given[0]
    others = {"steps": ("every",), "frozen": ("frames",), "keys": ("frames", "ease")}[form]
    for key in spec:
        if key not in (form,) + others:
            raise check.at(key).error(f"is not used with {form!r} "
                                      f"(it takes {', '.join((form,) + others)})")
    if form == "steps":
        lo, hi = check.at("steps").numbers(spec["steps"], 2)
        if lo > hi:
            raise check.at("steps").error(f"expected [first, last] with first <= last, got [{lo:g}, {hi:g}]")
        every = check.at("every").integer(spec.get("every", 1), minimum=1)
        chosen = [s for s in sorted(saved) if lo <= s <= hi][::every]
        if not chosen:
            raise check.at("steps").error(
                f"no saved step in [{lo:g}, {hi:g}] (saved: {min(saved)} to {max(saved)})")
        return ShotTime(chosen)
    if form == "frozen":
        value = check.at("frozen").number(spec["frozen"])
        n = check.at("frames").integer(spec.get("frames", 1), minimum=1)
        return ShotTime([nearest_step(value, saved)] * n)
    # keys
    track_spec = {k: spec[k] for k in ("keys", "ease") if k in spec}
    try:
        track = TimeTrack(track_spec, name="time")
    except ValueError as exc:
        raise check.wrap(exc) from None
    last = track.track.frames[-1]
    n = check.at("frames").integer(spec["frames"], minimum=1) if "frames" in spec \
        else int(last) + 1
    return ShotTime([track.step(i, saved) for i in range(n)])
