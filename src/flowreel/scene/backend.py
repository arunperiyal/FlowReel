"""Off-screen OpenGL backend for rendering (plan Section 7.5).

VTK picks its render window class when the first window of a process is made, from the
``VTK_DEFAULT_OPENGL_WINDOW`` environment variable. FlowReel sets that variable, so the
choice is made per process and every frame of a render uses the same one:

* ``osmesa``: Mesa's software renderer (``libOSMesa``). Needs no GPU and no display;
  on a many-core workstation it is the faster choice, and it gives the same pixels on
  every machine with the same Mesa.
* ``egl``: a GPU (or Mesa's EGL) without a display, as on airavata's nodes.
* ``x``: an X window drawn off-screen; needs ``DISPLAY``. Only when forced.
* ``auto`` (default): ``osmesa`` when ``libOSMesa`` is installed, else ``egl`` when
  ``libEGL`` is, else VTK's own default.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

BACKENDS = ("auto", "osmesa", "egl", "x")
WINDOW_CLASS = {"osmesa": "vtkOSOpenGLRenderWindow", "egl": "vtkEGLRenderWindow",
                "x": "vtkXOpenGLRenderWindow"}
ENV = "VTK_DEFAULT_OPENGL_WINDOW"
_LIBS = {"osmesa": ("libOSMesa.so.8", "libOSMesa.so", "OSMesa"),
         "egl": ("libEGL.so.1", "libEGL.so", "EGL")}


def installed(backend: str) -> bool:
    """True when the library ``backend`` needs can be loaded (``x``: ``DISPLAY`` is set).

    Looks in the environment's ``lib`` folder first (a conda environment ships Mesa
    there), then where the system loader looks.
    """
    if backend == "x":
        return bool(os.environ.get("DISPLAY"))
    names = _LIBS[backend]
    if any((Path(sys.prefix) / "lib" / name).exists() for name in names[:-1]):
        return True
    for name in names[:-1]:
        try:
            ctypes.CDLL(name)
            return True
        except OSError:
            pass
    return ctypes.util.find_library(names[-1]) is not None


def choose(backend: str = "auto") -> str | None:
    """The backend to use for ``backend`` (one of :data:`BACKENDS`).

    ``auto`` gives ``osmesa`` when installed, else ``egl``, else ``None`` (VTK's
    default window). A forced backend is returned as it is, even if it is not
    installed, so that the render fails loudly instead of silently using another.
    """
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r} (one of: {', '.join(BACKENDS)})")
    if backend != "auto":
        return backend
    for name in ("osmesa", "egl"):
        if installed(name):
            return name
    return None


def environment(backend: str | None, threads: int | None = None) -> dict[str, str]:
    """Environment variables that select ``backend`` and cap threads at ``threads``.

    ``backend`` is a result of :func:`choose`. ``threads`` limits Mesa's software
    rasteriser (``LP_NUM_THREADS``), BLAS and OpenMP, and VTK's SMP tools, so that
    ``jobs`` processes of ``threads`` threads each load the machine as asked.
    """
    env = {}
    if backend:
        env[ENV] = WINDOW_CLASS[backend]
    if threads:
        n = str(int(threads))
        for var in ("LP_NUM_THREADS", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                    "MKL_NUM_THREADS", "VTK_SMP_MAX_THREADS"):
            env[var] = n
    return env


def use(backend: str = "auto", threads: int | None = None) -> str | None:
    """Select ``backend`` for windows made from now on in this process; returns it."""
    chosen = choose(backend)
    os.environ.update(environment(chosen, threads))
    return chosen


def window_class(plotter) -> str:
    """Name of the VTK render window class a plotter uses (to check the backend)."""
    return type(plotter.ren_win).__name__
