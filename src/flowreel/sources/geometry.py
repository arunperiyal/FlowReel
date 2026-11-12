"""The ``geometry`` adapter: a parametric body built in code, with no flow data
(docs/PLAN.md, Section 5.3)."""
from __future__ import annotations

import inspect
from typing import Any, Mapping

import pandas as pd
import pyvista as pv

from flowreel.box import Box
from flowreel.sources.bodies import get_body


class GeometrySource:
    """A registered body as a :class:`~flowreel.sources.Source`.

    Arguments:
        body: name of a registered body (see :mod:`flowreel.sources.bodies`).
        params: the body's parameters, as plain values. Unknown names raise ``TypeError``
            here, not at the first frame.
        frames: number of steps; ``steps()`` is ``0 .. frames - 1`` (default 1).
        dt: time of one step, so ``time = step * dt`` (default 1).
        name: label of the source.

    There is no flow: ``fields()`` is empty and ``flow`` raises ``LookupError``. The
    parameters do not depend on the step here; a shot animates them by calling
    :meth:`build` with the values of its tracks.
    """

    def __init__(self, body: str, *, params: Mapping[str, Any] | None = None,
                 frames: int = 1, dt: float = 1.0, name: str = "geometry"):
        if int(frames) < 1:
            raise ValueError("frames must be at least 1")
        self.name = name
        self.body_name = body
        self._function = get_body(body)
        self._params = dict(params or {})
        self._bind(self._params)
        self._frames = int(frames)
        self._dt = float(dt)
        self._built: pv.PolyData | None = None

    def _bind(self, params: Mapping[str, Any]) -> None:
        """Check ``params`` against the body's signature."""
        try:
            inspect.signature(self._function).bind(**params)
        except TypeError as err:
            accepted = ", ".join(inspect.signature(self._function).parameters)
            raise TypeError(f"body {self.body_name!r}: {err}; it takes {accepted}") from None

    @property
    def params(self) -> dict[str, Any]:
        """A copy of the parameters the source was made with."""
        return dict(self._params)

    def build(self, **overrides) -> pv.PolyData:
        """The body with ``overrides`` replacing the source's parameters.

        This is what a track drives: ``build(cut_front=3.2)`` for one frame.
        """
        params = {**self._params, **overrides}
        self._bind(params)
        return self._function(**params)

    def _default(self) -> pv.PolyData:
        if self._built is None:
            self._built = self.build()
        return self._built

    def steps(self) -> list[int]:
        """Step numbers ``0 .. frames - 1``."""
        return list(range(self._frames))

    def time(self, step: int) -> float:
        """``step * dt``."""
        self._check(step)
        return step * self._dt

    def _check(self, step: int) -> None:
        if not 0 <= step < self._frames:
            raise KeyError(f"{self.name}: no step {step}; steps run from 0 to {self._frames - 1}")

    def fields(self) -> list[str]:
        """Empty: a geometry source has no flow fields."""
        return []

    def flow(self, step: int, fields: list[str], crop: Box | None) -> pv.UnstructuredGrid:
        """Always raises ``LookupError``: a geometry source has no flow data."""
        raise LookupError(f"{self.name}: a geometry source has no flow data, only the body "
                          f"{self.body_name!r}; use body(step), or a layer that needs no flow")

    def bodies(self) -> list[str]:
        """The one body's name."""
        return [self.body_name]

    def body(self, step: int, name: str | None = None) -> pv.PolyData:
        """The surface built from the source's parameters (the same at every step)."""
        self._check(step)
        if name not in (None, self.body_name):
            raise KeyError(f"{self.name}: no body {name!r}; bodies: {self.body_name}")
        return self._default().copy()

    def bounds(self) -> Box:
        """Bounds of the body built from the source's parameters."""
        return Box.from_bounds(self._default().bounds)

    def series(self, name: str) -> pd.DataFrame:
        """A geometry source has no time series: always raises ``KeyError``."""
        raise KeyError(f"{self.name}: a geometry source has no time series (asked for {name!r})")

    def memory_per_step(self, crop: Box | None) -> float:
        """Memory in GB of the body's surface (``crop`` is ignored: the body is not cropped)."""
        mesh = self._default()
        arrays = sum(mesh.point_data[k].nbytes for k in mesh.point_data.keys())
        return (mesh.points.nbytes + mesh.faces.nbytes + arrays) / 1e9
