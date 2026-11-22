"""What a frame of a shot costs, kept beside its frames (plan Section 19.6).

A job array is sized from one frame's peak memory and seconds. Both are measured, not
guessed: every :func:`~flowreel.scene.rendering.render` that draws frames records the
largest peak and the middle time of its frames, and ``shot memory`` records the frame it
draws. There is one record per frame folder (``frames/reveal/``, or a draft's own folder,
since a draft costs less), so the next render, on any machine sharing the folder, is
sized from the last one. In a project it is machine state, kept in
``.flowreel/measured/<frame folder>.json`` at the root (``.flowreel/measured/frames/reveal.json``);
for a frame folder outside one, ``.measured.json`` inside the folder.
"""
from __future__ import annotations

import json
import os
import socket
import statistics
import time as _time
from dataclasses import asdict, dataclass
from pathlib import Path

FILE = ".measured.json"


@dataclass(frozen=True)
class Measured:
    """One frame's cost: ``peak_bytes`` of its process, ``seconds`` to draw it (the
    middle of the frames drawn), with ``threads`` per process, from ``frames`` frames,
    on ``host`` at ``when`` (local time, ``YYYY-MM-DD HH:MM``)."""

    peak_bytes: int
    seconds: float
    threads: int
    frames: int
    host: str
    when: str

    def text(self) -> str:
        """``0.98 GB and 3.2 s a frame (12 frames, 1 thread, node1, 2026-11-21 04:10)``."""
        return (f"{self.peak_bytes / 1024 ** 3:.2f} GB and {self.seconds:.1f} s a frame "
                f"({self.frames} frame{'s' * (self.frames != 1)}, {self.threads} "
                f"thread{'s' * (self.threads != 1)}, {self.host}, {self.when})")


def path(folder: str | Path) -> Path:
    """The record of the frame folder ``folder`` (see the module)."""
    from flowreel.project.paths import STATE, find_root
    folder = Path(folder)
    full = folder.expanduser().resolve()
    root = find_root(full)
    if root is not None:
        try:
            rel = full.relative_to(root)
        except ValueError:
            rel = None
        if rel is not None and rel.parts:
            return root / STATE / "measured" / f"{rel}.json"
    return folder / FILE


def load(folder: str | Path) -> Measured | None:
    """The record of ``folder``, or ``None`` when there is none (or it cannot be read).
    A ``.measured.json`` left in the folder by an older FlowReel is read when the
    project has none."""
    for p in dict.fromkeys((path(folder), Path(folder) / FILE)):
        try:
            return Measured(**json.loads(p.read_text()))
        except (OSError, ValueError, TypeError):
            continue
    return None


def save(folder: str | Path, measured: Measured) -> Path:
    """Write ``measured`` as the record of ``folder`` (atomically); returns its path."""
    p = path(folder)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f"{FILE}.{os.getpid()}.part")
    tmp.write_text(json.dumps(asdict(measured), indent=1) + "\n")
    os.replace(tmp, p)
    return p


def from_frames(peaks: list[int], seconds: list[float], threads: int) -> Measured | None:
    """A record from frames just drawn (their peaks and seconds), or ``None`` if none
    was measured."""
    pairs = [(p, s) for p, s in zip(peaks, seconds) if p > 0]
    if not pairs:
        return None
    return Measured(max(p for p, _ in pairs), round(statistics.median(s for _, s in pairs), 3),
                    int(threads), len(pairs), socket.gethostname().split(".")[0],
                    _time.strftime("%Y-%m-%d %H:%M"))
