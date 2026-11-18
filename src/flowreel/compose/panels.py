"""Panel types and the drawing loop (plan Section 9.2).

A panel type is a class registered under its ``type`` name. It reads its keys from the
panel file's ``options`` when made, then draws in two steps: :meth:`PanelType.build`
makes the axes and artists once, reading its data, and :meth:`PanelType.update` moves
them to a frame's time (and index). The loop builds the figure once per process and calls ``update`` for
each frame: building a figure costs far more than moving its lines, and the frames of
one panel differ only in time.

:func:`panel` draws a panel's frames into ``out/<name>/frame_00000.png``, the frames
split into ``jobs`` runs of consecutive frames, each run in its own process.

Each frame has a key (plan Section 11) from the panel's type, size and settings, the
style, the frame's time and the path, size and modification time of every file the
panel reads; a frame drawn before with the same key is skipped unless ``force``.
"""
from __future__ import annotations

import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from flowreel.compose.panel_file import PanelFile, frame_times, load
from flowreel.compose.style import style_key
from flowreel.scene.errors import Checker
from flowreel.scene.keys import KeyStore, code_version, digest
from flowreel.scene.rendering import FRAME_NAME

REGISTRY: dict[str, type] = {}
# Modules that register the built-in types.
TYPE_MODULES: tuple[str, ...] = ("flowreel.compose.series_panel", "flowreel.compose.phase_panel")
DPI = 100


class PanelType:
    """Base of the panel types.

    Subclasses set ``name`` and ``KEYS`` (their own keys of the panel file) and read
    them in :meth:`parse`. ``self.panel`` is the :class:`PanelFile`, ``self.style`` its
    style.
    """

    name = ""
    KEYS: tuple[str, ...] = ()

    def __init__(self, panel: PanelFile, check: Checker):
        self.panel = panel
        self.style = panel.style
        options = check.mapping(panel.options, self.KEYS)
        self.parse(options, check)

    def parse(self, options: dict, check: Checker) -> None:
        """Read the type's keys; raise errors through ``check``."""

    def files(self) -> list[Path]:
        """The files the panel reads (for its frames' keys)."""
        return []

    def settings(self) -> dict:
        """What, besides the style, time and files, decides the picture."""
        return {"options": self.panel.options}

    def build(self, figure) -> None:
        """Make the axes and artists on ``figure`` (style applied), reading the data."""
        raise NotImplementedError

    def update(self, time: float, index: int | None = None) -> None:
        """Move the artists to ``time``, the time of the panel's frame ``index`` (for
        panels that follow a shot frame by frame, such as the windows of a locator)."""
        raise NotImplementedError


def register(cls: type) -> type:
    """Class decorator: make ``cls`` the panel type ``cls.name``."""
    REGISTRY[cls.name] = cls
    return cls


def make(panel: PanelFile) -> PanelType:
    """The panel type object of ``panel``, its keys checked."""
    import importlib
    for module in TYPE_MODULES:
        importlib.import_module(module)
    check = Checker(panel.file)
    kind = check.at("type").choice(panel.type, sorted(REGISTRY))
    return REGISTRY[kind](panel, check)


@dataclass
class PanelReport:
    """What :func:`panel` did: the frame folder and, per frame asked for,
    ``(index, path, status)``, status ``drawn`` or ``skipped``."""

    folder: Path
    frames: list[tuple[int, Path, str]] = field(default_factory=list)

    def count(self, status: str) -> int:
        """Number of frames with ``status``."""
        return sum(f[2] == status for f in self.frames)


def panel(pf, out: str | Path = "frames", *, times: Iterable[float] | None = None,
          frames: Iterable[int] | None = None, jobs: int = 1, force: bool = False,
          processes: bool = True,
          progress: Callable[[tuple[int, Path, str]], None] | None = None) -> PanelReport:
    """Draw the frames of ``pf`` (a :class:`PanelFile` or a panel file).

    Frame ``i`` is drawn at ``times[i]``: the panel's own times
    (:func:`~flowreel.compose.panel_file.frame_times`) unless ``times`` is given.
    ``frames`` limits the frames drawn. Frames go to ``out/<name>/frame_00000.png``;
    ``jobs`` runs of consecutive frames are drawn at once, each in its own process,
    which builds the figure once (``processes=False`` draws here, for debugging).
    A frame whose file exists with the same key (:func:`frame_key`) is skipped unless
    ``force``.
    """
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, got {jobs}")
    pf = pf if isinstance(pf, PanelFile) else load(pf)
    kind = make(pf)                      # check the keys before any work
    times = list(frame_times(pf) if times is None else times)
    indices = _frames(frames, len(times), pf)
    folder = Path(out) / pf.name
    folder.mkdir(parents=True, exist_ok=True)
    report = PanelReport(folder)
    results = {}
    store = KeyStore(folder)
    base = key_parts(pf, kind)
    keys = {i: frame_key(base, times[i]) for i in indices}

    def done(entry):
        results[entry[0]] = entry
        if entry[2] == "drawn":
            store.put(entry[1].name, keys[entry[0]])
        if progress:
            progress(entry)

    work = []
    for i in indices:
        path = folder / FRAME_NAME.format(i)
        if not force and store.fresh(path, keys[i]):
            done((i, path, "skipped"))
        else:
            work.append((i, times[i], str(path)))
    if work and (not processes or jobs == 1 or len(work) < 2):
        for entry in draw_run(pf, work, kind):
            done(entry)
    elif work:
        ctx = multiprocessing.get_context("spawn")
        runs = _runs(work, jobs)
        with ProcessPoolExecutor(max_workers=len(runs), mp_context=ctx) as pool:
            for fut in as_completed([pool.submit(draw_run, pf, run) for run in runs]):
                for entry in fut.result():
                    done(entry)
    report.frames = [results[i] for i in indices]
    return report


def key_parts(pf: PanelFile, kind: PanelType) -> dict:
    """What decides every frame of a panel but its time: the code, the type, size and
    settings, the style, and each file read (resolved path, size, modification time)."""
    stamps = []
    for f in kind.files():
        f = Path(f)
        try:
            st = f.stat()
            stamps.append([str(f.resolve()), st.st_size, st.st_mtime_ns])
        except OSError:
            stamps.append([str(f), None, None])
    return {"code": code_version("compose"), "type": pf.type, "size": list(pf.size),
            "settings": kind.settings(), "style": style_key(pf.style), "files": stamps}


def frame_key(parts: dict, time: float) -> str:
    """The key of the frame drawn at ``time``; equal keys, equal pictures."""
    return digest({**parts, "time": float(time)})


def _frames(frames, n: int, pf: PanelFile) -> list[int]:
    if frames is None:
        return list(range(n))
    out = sorted(set(int(i) for i in frames))
    bad = [i for i in out if not 0 <= i < n]
    if bad:
        raise Checker(pf.file).error(f"frame {bad[0]} is outside the panel's 0..{n - 1}")
    return out


def _runs(work: list, jobs: int) -> list[list]:
    """``work`` cut into at most ``jobs`` runs of consecutive frames, of near equal
    length."""
    n = min(jobs, len(work))
    edges = [round(k * len(work) / n) for k in range(n + 1)]
    return [work[a:b] for a, b in zip(edges, edges[1:]) if b > a]


def draw_run(pf: PanelFile, work: list, kind: PanelType | None = None) -> list:
    """Draw ``work`` (``(index, time, path)`` entries) with one figure; returns the
    entries ``(index, path, "drawn")``."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from PIL import Image
    kind = kind or make(pf)
    out = []
    with pf.style.applied():
        figure = Figure(figsize=(pf.size[0] / DPI, pf.size[1] / DPI), dpi=DPI)
        canvas = FigureCanvasAgg(figure)
        figure.patch.set_facecolor(pf.style.background)
        kind.build(figure)
        for index, time, path in work:
            kind.update(time, index)
            canvas.draw()
            picture = Image.frombuffer("RGBA", canvas.get_width_height(),
                                       canvas.buffer_rgba(), "raw", "RGBA", 0, 1).convert("RGB")
            path = Path(path)
            tmp = path.with_name(path.stem + ".part.png")
            picture.save(tmp)
            os.replace(tmp, path)       # a frame file is never half written
            out.append((index, path, "drawn"))
    return out
