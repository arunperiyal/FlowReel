"""Shared fixtures: small generated flows, never real data."""
import numpy as np
import pandas as pd
import pytest
import pyvista as pv

from flowreel.box import Box


class ToySource:
    """A tiny in-memory Source: a solid-body vortex on a 9x9x5 grid with a sphere body."""

    name = "toy"

    def __init__(self, n_steps: int = 3, dt: float = 0.5):
        self._steps = list(range(0, 10 * n_steps, 10))
        self._dt = dt

    def steps(self):
        return list(self._steps)

    def time(self, step):
        return self._steps.index(step) * self._dt

    def fields(self):
        return ["U", "V", "W", "p"]

    def flow(self, step, fields, crop):
        g = pv.ImageData(dimensions=(9, 9, 5), spacing=(0.25, 0.25, 0.25),
                         origin=(-1, -1, 0)).cast_to_unstructured_grid()
        x, y = g.points[:, 0], g.points[:, 1]
        omega = 1.0 + 0.1 * self._steps.index(step)
        data = {"U": -omega * y, "V": omega * x, "W": np.zeros(g.n_points),
                "p": 0.5 * omega**2 * (x**2 + y**2)}
        for f in fields:
            g.point_data[f] = data[f]
        if crop is not None:
            keep = crop.contains(g.cell_centers().points)
            g = g.extract_cells(np.flatnonzero(keep))
        return g

    def body(self, step):
        return pv.Sphere(radius=0.2, center=(0, 0, 0.5))

    def bounds(self):
        return Box((-1, -1, 0), (1, 1, 1))

    def series(self, name):
        t = [self.time(s) for s in self._steps]
        return pd.DataFrame({"time": t, "value": np.arange(len(t), dtype=float)})

    def memory_per_step(self, crop):
        return 1e-6


@pytest.fixture
def toy_source():
    return ToySource()
