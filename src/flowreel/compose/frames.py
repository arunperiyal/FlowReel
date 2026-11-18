"""Frames of a layout matched by index across its tiles (plan Section 9.1).

Every tile is a folder of ``frame_00000.png`` files, as ``shot render`` writes them.
Composed frame ``i`` puts frame ``i`` of each tile together, so tiles rendered from
shots of the same length line up frame by frame. A tile that lacks frame ``i`` is an
error, because a missing frame usually means a render that did not finish; with
``missing: hold`` the tile shows its nearest earlier frame instead (its first before
it starts), for a tile that is meant to be shorter, such as a still.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from pathlib import Path

from flowreel.scene.errors import Checker

FRAME = re.compile(r"frame_(\d{5,})\.png")


def frame_files(folder: str | Path) -> dict[int, Path]:
    """The frames in ``folder`` by index, from ``frame_NNNNN.png`` names (half-written
    ``.part.png`` files and other files are left out); empty if the folder is missing."""
    folder = Path(folder)
    if not folder.is_dir():
        return {}
    out = {}
    for path in folder.iterdir():
        m = FRAME.fullmatch(path.name)
        if m:
            out[int(m.group(1))] = path
    return out


@dataclass
class FrameMatch:
    """Which file each tile shows in each composed frame.

    ``indices`` are the composed frames, in order: every index that some tile has.
    ``files[i]`` lists, per tile, the file shown in frame ``i``; ``held[i]`` the tiles
    (by position) that hold a frame there."""

    indices: list[int]
    files: dict[int, list[Path]]
    held: dict[int, list[int]]


def match(layout, frames: dict | None = None) -> FrameMatch:
    """Match the frames of ``layout``'s tiles by index.

    ``frames`` maps tile positions to their ``{index: path}`` (read from the folders
    when not given). Raises :class:`~flowreel.scene.errors.ConfigError` at the tile's
    key path when a tile has no frames, or lacks one and the layout does not hold."""
    check = Checker(layout.file)
    per_tile = []
    def at(t):
        entry = layout.tiles[t].entry
        return check.at("tiles", t if entry is None else entry, "frames")

    for t, tile in enumerate(layout.tiles):
        found = frames[t] if frames is not None else frame_files(tile.frames)
        if not found:
            raise at(t).error(f"no frame_NNNNN.png files in {tile.frames}")
        per_tile.append(found)
    indices = sorted(set().union(*per_tile))
    files: dict[int, list[Path]] = {}
    held: dict[int, list[int]] = {}
    for t, found in enumerate(per_tile):
        have = sorted(found)
        for i in indices:
            if i in found:
                files.setdefault(i, []).append(found[i])
                continue
            if layout.missing != "hold":
                raise at(t).error(
                    f"{layout.tiles[t].frames} has no frame {i} (it has {_ranges(have)}); "
                    "render it, or set 'missing: hold' to show the nearest earlier frame")
            k = bisect.bisect_right(have, i) - 1
            files.setdefault(i, []).append(found[have[max(k, 0)]])
            held.setdefault(i, []).append(t)
    return FrameMatch(indices, files, held)


def _ranges(numbers: list[int]) -> str:
    """``[0, 1, 2, 5]`` as ``0-2, 5``."""
    parts, start = [], None
    for a, b in zip(numbers, numbers[1:] + [None]):
        start = a if start is None else start
        if b != a + 1:
            parts.append(f"{start}" if start == a else f"{start}-{a}")
            start = None
    return ", ".join(parts)
