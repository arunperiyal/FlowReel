"""What a project holds, and removing what it made (plan Section 13: ``project info`` and
``project clean``).

:func:`info` looks without changing anything: the bodies of ``flowreel.yml``, the shot
files and their sources, the views and tracks of ``cameras.yml``, the film, the data
links, and the size of everything generated. A file that does not load is reported
with its error rather than stopping the report, since ``info`` is where one looks when
something is wrong.

:func:`clean` removes generated output: the caches (``.flowreel/cache/``), the frames
(``frames/``) or the finished clips (``clips/``). It never touches what a person wrote,
the data, or the measured frame costs and job records in ``.flowreel/``, which are small
and size the next Slurm job. A folder that is a symbolic link is skipped, not followed:
what it points to may be shared.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.project.paths import CAMERAS_FILE, FILM_FILE, OUTPUTS, PROJECT_FILE, STATE

#: Folders under the root that hold no file written by hand.
SKIP = (*OUTPUTS, STATE, "data", "jobs", ".git")
#: What ``project clean`` can remove, by option, as folders under the root.
CLEANABLE = {"cache": f"{STATE}/cache", "frames": "frames", "clips": "clips"}


def size_of(path: Path) -> int:
    """Bytes in ``path`` (a file, or a folder and everything below it); links are not
    followed. 0 when it does not exist."""
    if path.is_symlink() or not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for folder, _, files in os.walk(path):
        for name in files:
            p = Path(folder) / name
            if not p.is_symlink():
                total += p.stat().st_size
    return total


def human(n: int) -> str:
    """``1.2 GB``, ``340 kB``, ``0 B``: bytes in powers of 1000."""
    for unit in ("B", "kB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n} B"


@dataclass
class ShotEntry:
    """A shot file: its ``path`` (relative to the root), ``name`` and ``source`` as
    written, the ``frames`` drawn in ``frames/<name>/``, the ``drafts`` in its draft
    folders (``frames/<name>@<W>x<H>/``) and an ``error`` when it cannot be read."""

    path: str
    name: str | None = None
    source: str | None = None
    frames: int = 0
    drafts: int = 0
    error: str | None = None


@dataclass
class ProjectInfo:
    """What :func:`info` found. Sizes are bytes; ``errors`` are lines about files that
    did not load."""

    root: Path
    bodies: list[str] = field(default_factory=list)
    shots: list[ShotEntry] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    tracks: list[str] = field(default_factory=list)
    film: str | None = None
    links: list[tuple[str, str]] = field(default_factory=list)
    sizes: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    @property
    def sources(self) -> list[str]:
        """The sources the shots read, each once, in order."""
        return list(dict.fromkeys(s.source for s in self.shots if s.source))

    def text(self) -> str:
        """The report, for the terminal."""
        def names(items):
            return ", ".join(items) if items else "none"
        lines = [f"project {self.root}"]
        if self.links:
            lines.append("data:    " + ", ".join(f"{n} -> {t}" for n, t in self.links))
        lines.append(f"source:  {names(self.sources) if self.shots else 'none (no shot yet)'}")
        lines.append(f"bodies:  {names(self.bodies)}")
        lines.append(f"shots:   {len(self.shots) or 'none'}")
        for s in self.shots:
            what = s.error or (f"{s.name}, {s.frames} frame{'s' * (s.frames != 1)} drawn"
                               + (f" ({s.drafts} in drafts)" if s.drafts else ""))
            lines.append(f"  {s.path}: {what}")
        lines.append(f"cameras: views {names(self.views)}; tracks {names(self.tracks)}")
        lines.append(f"film:    {self.film or 'none'}")
        lines.append("output:  " + ", ".join(f"{k} {human(v)}" for k, v in self.sizes.items()))
        lines += [f"error:   {e}" for e in self.errors]
        return "\n".join(lines)


def shot_files(root: Path) -> list[Path]:
    """The YAML files under ``root`` that are shots (a mapping with ``source`` and
    ``layers``), outside the generated folders and the data."""
    from flowreel.yamlfile import read_yaml
    found = []
    for folder, dirs, files in os.walk(root):
        here = Path(folder)
        if here == root:
            dirs[:] = [d for d in dirs if d not in SKIP]
        dirs.sort()
        for name in sorted(files):
            p = here / name
            if p.suffix not in (".yml", ".yaml") or (here == root and name in (
                    PROJECT_FILE, CAMERAS_FILE, FILM_FILE)):
                continue
            try:
                data = read_yaml(p)
            except Exception:
                continue
            if isinstance(data, dict) and "source" in data and "layers" in data:
                found.append(p)
    return found


def _source_text(value) -> str:
    """A shot's ``source`` as one line: ``adapter:path``, then its body files, if any
    (``body cylinder=wall.vtp``)."""
    if not isinstance(value, dict):
        return str(value)
    text = ":".join(str(value[k]) for k in ("adapter", "path") if k in value)
    body = value.get("body")
    if isinstance(body, dict):
        text += " body " + ", ".join(f"{name}={path}" for name, path in body.items())
    elif body is not None:
        text += (" body " if "path" in value else ":") + str(body)
    return text


def info(root: str | Path) -> ProjectInfo:
    """What the project at ``root`` holds (see the module)."""
    from flowreel.project import load_project
    from flowreel.yamlfile import read_yaml
    root = Path(root).resolve()
    out = ProjectInfo(root)
    try:
        out.bodies = list(load_project(root).bodies)
    except Exception as exc:                       # reported, not raised: see the module
        out.errors.append(str(exc))
    for p in shot_files(root):
        entry = ShotEntry(str(p.relative_to(root)))
        try:
            data = read_yaml(p)
            entry.name, entry.source = str(data.get("name", p.stem)), _source_text(data["source"])
            entry.frames = len(list((root / "frames" / entry.name).glob("frame_*.png")))
            entry.drafts = len(list((root / "frames").glob(f"{entry.name}@*/frame_*.png")))
        except Exception as exc:
            entry.error = str(exc)
        out.shots.append(entry)
    cameras = root / CAMERAS_FILE
    if cameras.exists():
        try:
            from flowreel.scene.camera_path import load_tracks
            from flowreel.scene.views import load_views
            views = load_views(cameras)
            out.views, out.tracks = list(views), list(load_tracks(cameras, views))
        except Exception as exc:
            out.errors.append(str(exc))
    film = root / FILM_FILE
    if film.exists():
        from flowreel.film.schema import load
        from flowreel.film.timeline import timeline
        try:
            f = load(film)
        except Exception as exc:
            out.film = f"{FILM_FILE}: does not load"
            out.errors.append(str(exc))
        else:
            out.film = f"{FILM_FILE}: {len(f.shots)} shot{'s' * (len(f.shots) != 1)}"
            try:                                  # needs the frames: a new film has none
                out.film += f", {timeline(f).length:.1f} s planned"
            except Exception as exc:
                out.film += f", length not known yet ({getattr(exc, 'problem', exc)})"
    data = root / "data"
    if data.is_dir():
        out.links = [(p.name, str(p.readlink())) for p in sorted(data.iterdir()) if p.is_symlink()]
    out.sizes = {"frames/": size_of(root / "frames"), "clips/": size_of(root / "clips"),
                 f"{STATE}/": size_of(root / STATE)}
    return out


@dataclass
class Removed:
    """What :func:`clean` removed (or, in a dry run, would remove): ``(path, bytes)``
    pairs, and ``skipped`` folders that are links."""

    removed: list[tuple[Path, int]] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    dry_run: bool = False

    @property
    def total(self) -> int:
        """Bytes removed (or, in a dry run, that would be) in all."""
        return sum(n for _, n in self.removed)


def clean(root: str | Path, what=("cache",), dry_run: bool = False) -> Removed:
    """Remove the generated folders ``what`` (keys of :data:`CLEANABLE`) of the project
    at ``root``; with ``dry_run``, only say what would go. Returns :class:`Removed`."""
    root = Path(root).resolve()
    bad = [w for w in what if w not in CLEANABLE]
    if bad:
        raise ValueError(f"cannot clean {bad[0]!r}: one of {', '.join(CLEANABLE)}")
    done = Removed(dry_run=dry_run)
    for w in what:
        path = root / CLEANABLE[w]
        if path.is_symlink():
            done.skipped.append(path)
            continue
        if not path.exists():
            continue
        done.removed.append((path, size_of(path)))
        if not dry_run:
            shutil.rmtree(path)
    return done
