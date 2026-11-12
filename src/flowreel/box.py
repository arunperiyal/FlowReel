"""Axis-aligned boxes, used for the domain bounds and for cropping while reading."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Box:
    """An axis-aligned box ``lo <= x <= hi`` in the source's length unit.

    ``lo`` and ``hi`` are ``(x, y, z)`` tuples. Use :meth:`from_bounds` for VTK's
    ``(xmin, xmax, ymin, ymax, zmin, zmax)`` order.
    """

    lo: tuple[float, float, float]
    hi: tuple[float, float, float]

    def __post_init__(self) -> None:
        lo = tuple(float(v) for v in self.lo)
        hi = tuple(float(v) for v in self.hi)
        if len(lo) != 3 or len(hi) != 3:
            raise ValueError("Box needs three coordinates for lo and for hi")
        if any(a > b for a, b in zip(lo, hi)):
            raise ValueError(f"Box lo {lo} is above hi {hi}")
        object.__setattr__(self, "lo", lo)
        object.__setattr__(self, "hi", hi)

    @classmethod
    def from_bounds(cls, bounds) -> "Box":
        """Build from VTK bounds ``(xmin, xmax, ymin, ymax, zmin, zmax)``."""
        b = tuple(bounds)
        if len(b) != 6:
            raise ValueError("bounds need six numbers")
        return cls(lo=(b[0], b[2], b[4]), hi=(b[1], b[3], b[5]))

    def to_bounds(self) -> tuple[float, ...]:
        """Return VTK bounds ``(xmin, xmax, ymin, ymax, zmin, zmax)``."""
        return (self.lo[0], self.hi[0], self.lo[1], self.hi[1], self.lo[2], self.hi[2])

    @property
    def size(self) -> tuple[float, float, float]:
        """Edge lengths."""
        return tuple(h - l for l, h in zip(self.lo, self.hi))

    @property
    def center(self) -> tuple[float, float, float]:
        """Centre point."""
        return tuple((l + h) / 2 for l, h in zip(self.lo, self.hi))

    def contains(self, points) -> np.ndarray:
        """Boolean mask of the ``(n, 3)`` points inside the box (edges included)."""
        p = np.atleast_2d(np.asarray(points, dtype=float))
        return np.all((p >= self.lo) & (p <= self.hi), axis=1)

    def intersects(self, other: "Box") -> bool:
        """True if the two boxes share at least one point."""
        return all(a <= d and c <= b for a, b, c, d in zip(self.lo, self.hi, other.lo, other.hi))

    def intersection(self, other: "Box") -> "Box | None":
        """The overlap, or ``None`` when the boxes do not touch."""
        if not self.intersects(other):
            return None
        return Box(tuple(max(a, c) for a, c in zip(self.lo, other.lo)),
                   tuple(min(b, d) for b, d in zip(self.hi, other.hi)))

    def expanded(self, margin: float) -> "Box":
        """A box grown by ``margin`` on every side (negative shrinks)."""
        return Box(tuple(l - margin for l in self.lo), tuple(h + margin for h in self.hi))
