"""Panels drawn at the film's output rate (plan Section 9.3).

The film shows flow frames at a lower rate than it plays (8 frames a second of flow in
a 24 frames a second film) and makes the frames between them by interpolation. A panel
laid over such frames must not be interpolated too: its dot and line end would smear.
It is drawn for every output frame instead, at a time between the two flow frames
around it, and held while the film holds (a freeze).

The film describes its output frames as **positions**: one number per output frame,
the flow frame it shows, fractional between two flow frames, the same number repeated
through a hold. :func:`output_positions` makes them from a rate and holds;
:func:`times_at` turns them into a panel's times.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np


def output_positions(n_frames: int, per_frame: int = 1,
                     holds: Iterable[tuple[float, int]] = ()) -> list[float]:
    """The positions of a film's output frames over ``n_frames`` flow frames.

    Each flow frame is followed by ``per_frame - 1`` frames between it and the next
    (``per_frame`` 3 turns 8 frames a second into 24): positions ``0, 1/3, 2/3, 1, ...``
    up to the last flow frame. ``holds`` are ``(position, count)`` pairs: when the film
    reaches ``position`` it shows it ``count`` more times (a freeze of ``count`` output
    frames); a position past the last frame holds at the end.
    """
    if n_frames < 1:
        raise ValueError(f"need at least one flow frame, got {n_frames}")
    if per_frame < 1:
        raise ValueError(f"per_frame must be at least 1, got {per_frame}")
    pending = sorted((float(at), int(count)) for at, count in holds)
    if any(count < 0 for _, count in pending):
        raise ValueError("a hold's count must not be negative")
    out: list[float] = []
    for k in range((n_frames - 1) * per_frame + 1):
        p = k / per_frame
        while pending and pending[0][0] <= p + 1e-9:
            at, count = pending.pop(0)
            out += [at] * count
        out.append(p)
    for at, count in pending:
        out += [float(n_frames - 1)] * count
    return out


def times_at(times, positions) -> list[float]:
    """The time at each of ``positions``: ``times[i]`` at a whole position ``i``, and
    linearly between ``times[i]`` and ``times[i + 1]`` between them. Positions before
    the first frame or after the last take its time (the panel holds)."""
    t = np.asarray(list(times), dtype=float)
    if not len(t):
        raise ValueError("the panel has no times")
    p = np.clip(np.asarray(list(positions), dtype=float), 0, len(t) - 1)
    return [float(v) for v in np.interp(p, np.arange(len(t)), t)]
