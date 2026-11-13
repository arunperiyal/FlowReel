"""The ``Source`` interface every data adapter implements (docs/PLAN.md, Section 5.1)."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd
import pyvista as pv

from flowreel.box import Box

#: Standard names adapters map their own names onto.
VELOCITY_COMPONENTS = ("U", "V", "W")
VELOCITY = "velocity"
PRESSURE = "p"


@runtime_checkable
class Source(Protocol):
    """Read access to one simulation (or one generated body).

    Velocity is ``U``, ``V``, ``W`` or the vector ``velocity``; pressure is ``p``.
    Units are the source's own. Derived fields are not the source's job: they are computed
    from velocity and pressure (Section 6).
    """

    name: str

    def steps(self) -> list[int]:
        """Saved step numbers, ascending."""
        ...

    def time(self, step: int) -> float:
        """Physical time of ``step``."""
        ...

    def fields(self) -> list[str]:
        """Names of the point fields the source can provide."""
        ...

    def flow(self, step: int, fields: list[str], crop: Box | None) -> pv.UnstructuredGrid:
        """The volume at ``step`` with the requested ``fields``, cropped to ``crop``.

        The crop is applied while reading where the format allows.
        """
        ...

    def body(self, step: int) -> pv.PolyData:
        """The wall surface at ``step``, deformed to that step."""
        ...

    def bounds(self) -> Box:
        """Bounds of the whole domain."""
        ...

    def series(self, name: str) -> pd.DataFrame:
        """A time series: a ``time`` column plus value columns."""
        ...

    def memory_per_step(self, crop: Box | None) -> float:
        """Estimated memory in GB for one step read with ``crop``, used to pick ``-j``."""
        ...
