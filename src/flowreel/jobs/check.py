"""Off-screen check: which OpenGL backends draw on this machine, and how fast.

Every job script runs this first (``python -m flowreel.jobs.check``), so a node without
a working off-screen OpenGL fails in seconds instead of after loading the data. Each
installed backend of :mod:`flowreel.scene.backend` draws a 64x64 sphere in a fresh
Python process with that backend's environment, so a crash or a hang of one backend is
reported and does not take the caller with it. ``x`` is tried only when ``DISPLAY`` is
set; ``osmesa`` and ``egl`` are tried without ``DISPLAY``, as on a compute node.

The exit code is 0 when the backend a render would use (``auto`` by default) works.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

from flowreel.scene import backend as backend_mod

#: Seconds a backend may take before it counts as hung.
TIMEOUT = 60.0

#: Starts the child's own reason for failing, to tell it from VTK's log lines, which
#: may be printed after it (VTK 9.7 warns about OSMesa as the process ends).
MARK = "flowreel-check: "

#: Drawn in the child process; ``argv[1]`` is the window class it must get, ``argv[2]``
#: the :data:`MARK` its reason for failing starts with.
SCRIPT = """
import sys
MARK = sys.argv[2]
import numpy as np
import pyvista as pv
plotter = pv.Plotter(off_screen=True, window_size=(64, 64))
plotter.set_background("black")
plotter.add_mesh(pv.Sphere(), color="white")
image = plotter.screenshot(return_img=True)
name = type(plotter.ren_win).__name__
plotter.close()
if name != sys.argv[1]:
    raise SystemExit(f"{MARK}VTK made a {name}, not a {sys.argv[1]}")
if not np.asarray(image).any():
    raise SystemExit(f"{MARK}the picture is blank")
"""


@dataclass(frozen=True)
class BackendResult:
    """One backend's check: ``status`` is ``works``, ``fails`` or ``not installed``;
    ``seconds`` the time the drawing process took (0 when not tried); ``error`` the last
    line of its error output when it fails."""

    backend: str
    status: str
    seconds: float = 0.0
    error: str = ""

    def text(self) -> str:
        """One line, e.g. ``egl      works in 1.9 s``."""
        line = f"{self.backend:<8} {self.status}"
        if self.status != "not installed":
            line += f" in {self.seconds:.1f} s"
        return line + (f": {self.error}" if self.error else "")


@dataclass(frozen=True)
class CheckReport:
    """The results, one per backend tried, and the backend ``asked`` resolves to
    (``chosen``; ``None``: none installed, VTK's default window)."""

    results: tuple[BackendResult, ...]
    asked: str
    chosen: str | None

    @property
    def ok(self) -> bool:
        """True when the chosen backend works."""
        return any(r.backend == self.chosen and r.status == "works" for r in self.results)

    @property
    def exit_code(self) -> int:
        """0 when the chosen backend works, else 1."""
        return 0 if self.ok else 1

    def text(self) -> str:
        """A short report for the terminal or a job's log."""
        lines = [r.text() for r in self.results]
        chosen = self.chosen or "none (no off-screen backend installed)"
        verdict = "works" if self.ok else "does NOT work"
        lines.append(f"{self.asked} -> {chosen}: {verdict}")
        return "\n".join(lines)


def candidates(environ=None) -> list[str]:
    """The backends to try: ``osmesa``, ``egl``, and ``x`` when ``DISPLAY`` is set."""
    env = os.environ if environ is None else environ
    return ["osmesa", "egl"] + (["x"] if env.get("DISPLAY") else [])


def try_backend(backend: str, timeout: float = TIMEOUT,
                extra_env: dict[str, str] | None = None) -> BackendResult:
    """Draw the test scene with ``backend`` in a fresh process; never raises for a
    failure of the drawing. ``extra_env`` is added to the child's environment (tests)."""
    if not backend_mod.installed(backend):
        return BackendResult(backend, "not installed")
    env = dict(os.environ)
    if backend != "x":
        env.pop("DISPLAY", None)
    env.update(backend_mod.environment(backend, threads=1))
    env.update(extra_env or {})
    want = backend_mod.WINDOW_CLASS[backend]
    start = time.perf_counter()
    try:
        done = subprocess.run([sys.executable, "-c", SCRIPT, want, MARK], env=env,
                              capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return BackendResult(backend, "fails", time.perf_counter() - start,
                             f"no picture after {timeout:g} s")
    seconds = time.perf_counter() - start
    if done.returncode == 0:
        return BackendResult(backend, "works", seconds)
    return BackendResult(backend, "fails", seconds, _last_line(done))


def check(backend: str = "auto", timeout: float = TIMEOUT,
          backends: list[str] | None = None) -> CheckReport:
    """Try each of ``backends`` (default :func:`candidates`) and say whether
    ``backend`` (one of :data:`~flowreel.scene.backend.BACKENDS`) works."""
    chosen = backend_mod.choose(backend)
    names = candidates() if backends is None else list(backends)
    if chosen and chosen not in names:
        names.append(chosen)
    return CheckReport(tuple(try_backend(n, timeout) for n in names), backend, chosen)


def _last_line(done: subprocess.CompletedProcess) -> str:
    for stream in (done.stderr, done.stdout):
        for line in reversed((stream or "").splitlines()):
            if line.startswith(MARK):
                return line[len(MARK):].strip()
    said = ""
    for stream in (done.stderr, done.stdout):
        lines = [line.strip() for line in (stream or "").splitlines() if line.strip()]
        if lines:
            said = lines[-1]
            break
    if done.returncode < 0:          # a crash (VTK 9.7 crashes on a missing window class)
        try:
            killed = f"killed by {signal.Signals(-done.returncode).name}"
        except ValueError:
            killed = f"killed by signal {-done.returncode}"
        return f"{killed}; last said: {said}" if said else killed
    return said or f"exit code {done.returncode}"


def main(argv: list[str] | None = None) -> int:
    """``python -m flowreel.jobs.check [--backend B] [--timeout S]``: print the report,
    return its exit code."""
    parser = argparse.ArgumentParser(
        prog="python -m flowreel.jobs.check",
        description="Draw a tiny scene with each off-screen backend and report which work.")
    parser.add_argument("--backend", default="auto", choices=backend_mod.BACKENDS,
                        help="the backend the render will use (default: auto)")
    parser.add_argument("--timeout", type=float, default=TIMEOUT,
                        help=f"seconds per backend before it counts as hung (default: {TIMEOUT:g})")
    args = parser.parse_args(argv)
    report = check(args.backend, args.timeout)
    print(report.text(), flush=True)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
