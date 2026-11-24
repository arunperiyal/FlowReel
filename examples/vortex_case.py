"""A generated flow case in VTK files: a solid-body vortex round a sphere.

Shared by the examples that need a small flow and no data (``flow_layers``,
``render_shot``, ``camera_editor``, ``anchored_caption``). ``write_vortex(folder)``
writes ``folder/vtk/flow_<step>.vtu`` (point arrays ``U``, ``V``, ``W``; velocity
``(-s y, s x, 0)``, ``s = 1 + SPIN * step``, so ``|u| = s r``) and ``folder/vtk/sphere.vtp``;
``make_project(folder, steps)`` makes a project there with the case as the tag ``vortex``.
Lengths are in the case's own unit; the sphere has radius 0.2 at (0, 0, 0.5) in a box
x, y in [-1, 1], z in [0, 1].
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pyvista as pv

SPIN = 0.5            # how much faster the vortex spins at each step


def write_vortex(folder: Path, steps: int = 1) -> Path:
    """Write ``steps`` flow files and the sphere under ``folder/vtk``; return that folder.
    Existing files are kept, so a second run draws the same frames."""
    out = folder / "vtk"
    out.mkdir(parents=True, exist_ok=True)
    for step in range(steps):
        path = out / f"flow_{step:04d}.vtu"
        if path.exists():
            continue
        grid = pv.ImageData(dimensions=(17, 17, 9), spacing=(0.125, 0.125, 0.125),
                            origin=(-1, -1, 0)).cast_to_unstructured_grid()
        x, y = grid.points[:, 0], grid.points[:, 1]
        spin = 1.0 + SPIN * step
        for name, value in {"U": -spin * y, "V": spin * x, "W": 0 * x}.items():
            grid.point_data[name] = value
        grid.save(path)
    if not (out / "sphere.vtp").exists():
        pv.Sphere(radius=0.2, center=(0, 0, 0.5)).save(out / "sphere.vtp")
    return out


def flowreel(folder: Path, *args: str) -> str:
    """Run ``flowreel ARGS`` in ``folder``; stop with its message if it fails."""
    done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder,
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(done.stderr or done.stdout)
    return done.stdout


def make_project(folder: Path, steps: int = 1) -> None:
    """A project in ``folder`` with the generated case as the tag ``vortex`` (written once)."""
    if (folder / "data" / "vortex" / "domain.yml").is_file():
        return
    write_vortex(folder, steps)
    if not (folder / "flowreel.yml").is_file():
        flowreel(folder, "project", "init", "--force")
    flowreel(folder, "data", "import", "vtk", "--path", "vtk", "--flow", "flow_*.vtu", "--body", "sphere=vtk/sphere.vtp",
             "--tag", "vortex")
