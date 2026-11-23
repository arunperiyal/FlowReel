"""The versions FlowReel declares and is tested on (plan Section 19.9, Phase 8 branch 2),
for ``flowreel doctor``.

:data:`TESTED` holds the oldest and newest versions of VTK and pyvista the test suite
runs on in CI (``.github/workflows/tests.yml``); :func:`minimums` reads the minimums
FlowReel declares (``pyproject.toml``, as installed).
"""
from __future__ import annotations

import re
from importlib import metadata

#: The oldest and newest versions (major.minor) the test suite runs on in CI. The oldest
#: are FlowReel's declared minimums (tests/test_doctor.py checks); the newest is raised
#: when CI's newest job passes on a new release.
TESTED = {"vtk": ("9.3", "9.7"), "pyvista": ("0.44", "0.49")}

def version_tuple(text: str) -> tuple[int, ...]:
    """The leading numbers of a version: ``9.7.2`` -> ``(9, 7, 2)``, ``2.1.1rc1`` ->
    ``(2, 1, 1)``."""
    numbers = []
    for part in text.split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        numbers.append(int(m.group()))
        if m.group() != part:
            break
    return tuple(numbers)


def minimums() -> dict[str, str]:
    """The minimum version FlowReel declares for each dependency that has one
    (``pyproject.toml``, as installed)."""
    out = {}
    for req in metadata.requires("flowreel") or []:
        if "extra ==" in req:
            continue
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*>=\s*([\d.]+)", req)
        if m:
            out[m.group(1)] = m.group(2)
    return out
