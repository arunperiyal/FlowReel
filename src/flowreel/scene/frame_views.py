"""The camera each frame was drawn with, kept beside the frames (plan Section 12).

A film shot names a folder of frames, not the shot file that drew them. So that a
caption can point at a place in the model, ``shot render`` records in the folder, for
every frame it draws or finds already drawn, the view the frame was drawn from, the
picture's size and the shot's stretch: ``<folder>/.views.json``, beside ``.keys.json``.

.. code-block:: json

    {"frame_00000.png": {"position": [-19, 13, -5], "focal": [6, 0, 8.5], "up": [0, 1, 0],
                         "view_angle": 30, "parallel": false, "parallel_scale": 1,
                         "size": [1920, 1080], "stretch": null}}

The view is the one the camera had, after ``fit`` and ``follow``; it is in the
coordinates the model is drawn in, so a model point is multiplied by ``stretch``
(``[sx, sy, sz]``, ``null`` for none) before it is projected (:meth:`DrawnView.pixels`).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from flowreel.scene.views import View

VIEWS_FILE = ".views.json"
VIEW_FIELDS = ("position", "focal", "up", "view_angle", "parallel", "parallel_scale")


@dataclass(frozen=True)
class DrawnView:
    """How one frame was drawn: its ``view``, the picture ``size`` (width, height) and
    the shot's ``stretch`` (x, y, z scale, or ``None``)."""

    view: View
    size: tuple[int, int]
    stretch: tuple[float, float, float] | None = None

    def pixels(self, points) -> np.ndarray:
        """Pixel ``(x, y)`` of model ``points`` (``(3,)`` or ``(N, 3)``) in the frame, and
        their depth: ``(N, 3)``, ``nan`` for a point at or behind the camera
        (:func:`flowreel.scene.projection.project`)."""
        from flowreel.scene.projection import project
        p = np.atleast_2d(np.asarray(points, float))
        if self.stretch is not None:
            p = p * np.asarray(self.stretch, float)
        return project(self.view, p, self.size)

    def as_dict(self) -> dict:
        """The record as written in ``.views.json``."""
        v = self.view
        return {"position": list(v.position), "focal": list(v.focal), "up": list(v.up),
                "view_angle": v.view_angle, "parallel": v.parallel,
                "parallel_scale": v.parallel_scale, "size": list(self.size),
                "stretch": None if self.stretch is None else list(self.stretch)}

    @classmethod
    def from_dict(cls, d: dict) -> "DrawnView":
        """A record read back from ``.views.json``."""
        view = View(tuple(map(float, d["position"])), tuple(map(float, d["focal"])),
                    tuple(map(float, d["up"])), float(d["view_angle"]), bool(d["parallel"]),
                    float(d["parallel_scale"]))
        stretch = d.get("stretch")
        return cls(view, (int(d["size"][0]), int(d["size"][1])),
                   None if stretch is None else tuple(map(float, stretch)))


def save_views(folder: str | Path, drawn: dict[str, DrawnView]) -> None:
    """Add ``drawn`` (frame file name to :class:`DrawnView`) to ``folder``'s record,
    keeping the other frames' entries; written through a temporary file."""
    path = Path(folder) / VIEWS_FILE
    try:
        record = json.loads(path.read_text())
    except (FileNotFoundError, ValueError):
        record = {}
    record.update({name: d.as_dict() for name, d in drawn.items()})
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, indent=0, sort_keys=True))
    os.replace(tmp, path)


def load_views(folder: str | Path) -> dict[str, DrawnView]:
    """The record of ``folder``: frame file name to :class:`DrawnView`; empty when the
    frames were not drawn by ``shot render`` (or before it kept the record)."""
    try:
        record = json.loads((Path(folder) / VIEWS_FILE).read_text())
    except (FileNotFoundError, ValueError):
        return {}
    return {name: DrawnView.from_dict(d) for name, d in record.items()}
