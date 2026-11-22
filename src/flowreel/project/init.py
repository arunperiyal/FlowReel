"""``flowreel project init``: a project folder, and its ``flowreel.yml`` with one body
per surface zone.

:func:`make_project` lays out the folder (plan Section 23, question 6): the folders
written by hand (:data:`~flowreel.project.paths.FOLDERS`), ``film.yml`` and
``cameras.yml`` at the root, a ``.gitignore`` for what is generated and for the data, and,
when asked, a symbolic link to the data in ``data/``. Data is linked and never copied:
it is large, and it belongs to the simulation, not the film. Files a person may have
edited (``film.yml``, ``cameras.yml``) are never overwritten.

Each zone of the source becomes a body under its zone's name. A slender zone becomes a
beam body, with its axis and diameter measured from the surface at one step
(:mod:`flowreel.project.measure`). The supports and series are left to fill, written commented out: a PLT file does not say how
a body is held, and a guess there would be drawn as if it were known. The result loads
as it is.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from dataclasses import dataclass, field

from flowreel.project.bodies import SUPPORTS
from flowreel.project.measure import AXES, diameter, long_axis
from flowreel.project.paths import CAMERAS_FILE, FILM_FILE, FOLDERS, IGNORED, PROJECT_FILE

COLUMN = 38


def _num(v: float) -> str:
    return f"{v:.4g}"


def _line(text: str, comment: str = "") -> str:
    return f"{text.ljust(COLUMN)}# {comment}" if comment else text


def _key(name: str) -> str:
    text = yaml.safe_dump(name, default_flow_style=True).strip()
    return text.removesuffix("...").strip()


def body_block(zone: str, surface) -> str:
    """The YAML of one declared body for ``zone``, measured from ``surface``."""
    pts = np.asarray(surface.points)
    ext = np.ptp(pts, axis=0)
    axis = long_axis(surface)
    lines = [f"  {_key(zone)}:", f"    zone: {_key(zone)}"]
    if axis is None:
        lines.append(_line("    # axis: x", "not slender, so not a beam: "
                           + " x ".join(_num(e) for e in ext) + "; give one to make it a beam"))
    else:
        k = AXES[axis]
        across = max(np.delete(ext, k))
        lines.append(_line(f"    axis: {axis}", f"measured: {_num(ext[k])} long, {_num(across)} across"))
        try:
            d = diameter(surface, axis)
            lines.append(_line(f"    diameter: {_num(d)}", "measured from the surface; check it"))
        except ValueError as exc:
            lines.append(_line("    # diameter: 1.0", f"could not measure ({exc})"))
        lo, hi = float(pts[:, AXES[axis]].min()), float(pts[:, AXES[axis]].max())
        lines += [_line("    # ends:", "how it is held: " + ", ".join(SUPPORTS)),
                  f"    #   - {{at: {_num(lo)}, support: clamped}}",
                  f"    #   - {{at: {_num(hi)}, support: clamped}}"]
    lines += [_line("    # series:", "time histories as CSV (docs/bodies.md)"),
              f"    #   displacement: {{file: data/{zone}_displacement.csv}}"]
    return "\n".join(lines)


def bodies_yaml(source, step: int | None = None, label: str | None = None) -> str:
    """The text of a ``flowreel.yml`` declaring every surface zone of ``source``, measured
    at ``step`` (default the first). ``label`` names the source in the header. Raises
    ``LookupError`` when the source has no surface zone."""
    zones = source.bodies()
    if not zones:
        raise LookupError(f"{source.name}: the source has no surface zone to declare; "
                          "write bodies: by hand (docs/bodies.md)")
    step = source.steps()[0] if step is None else step
    head = [f"# flowreel.yml written by `flowreel project init` from {label or source.name}"
            f" at step {step}.",
            "# Reference: docs/bodies.md. Axes and diameters are measured; supports and",
            "# series are left to fill (uncomment and edit).",
            "bodies:"]
    blocks = [body_block(z, source.body(step, z)) for z in zones]
    return "\n".join(head) + "\n" + "\n".join(blocks) + "\n"


EMPTY = """# flowreel.yml written by `flowreel project init` without a source.
# Reference: docs/project.md and docs/bodies.md. Declare the bodies here, or run
# `flowreel project init SOURCE --force` to measure them from the source.
# bodies:
#   cylinder: {zone: wall, axis: z, diameter: 1.0}
"""


def init_project(folder: str | Path, source=None, step: int | None = None, *,
                 label: str | None = None, force: bool = False) -> Path:
    """Write ``folder/flowreel.yml`` from ``source`` (:func:`bodies_yaml`), or a file
    with only comments without one; returns its path. Raises ``FileExistsError``
    unless ``force``."""
    path = Path(folder) / PROJECT_FILE
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists (use --force to overwrite)")
    text = EMPTY if source is None else bodies_yaml(source, step, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


@dataclass
class Made:
    """What :func:`make_project` did: the project ``root``, the files and folders it
    ``wrote``, those it ``kept`` as they were, and the data ``link`` (or ``None``)."""

    root: Path
    wrote: list[Path] = field(default_factory=list)
    kept: list[Path] = field(default_factory=list)
    link: Path | None = None


def gitignore_text(old: str = "") -> str:
    """``old`` (a ``.gitignore``'s text) with the lines of
    :data:`~flowreel.project.paths.IGNORED` it lacks added at the end."""
    have = {line.strip() for line in old.splitlines()}
    missing = [line for line in IGNORED if line not in have and line.rstrip("/") not in have]
    if not missing:
        return old
    head = "" if not old else old if old.endswith("\n") else old + "\n"
    return head + "# Made by FlowReel (docs/project.md): generated output and linked data\n" \
        + "\n".join(missing) + "\n"


def cameras_text(source=None, label: str | None = None) -> str:
    """A first ``cameras.yml``: one view ``main`` looking down -z with the source's
    domain in frame (a placeholder without a source), to replace with one picked in
    ``flowreel camera edit``."""
    from flowreel.scene.camera_file import view_line
    from flowreel.scene.views import View
    view = View((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), name="main")
    note = "a placeholder: no source was given"
    if source is not None:
        from flowreel.scene.framing import fit
        view = fit(view, source.bounds())
        note = f"the whole domain of {label or getattr(source, 'name', 'the source')}, from +z"
    return ("# cameras.yml written by `flowreel project init`: every shot and caption of\n"
            "# the project reads its views and tracks here. Reference: docs/cameras.md;\n"
            "# pick views and tracks with `flowreel camera edit`.\n"
            f"views:\n  - {view_line(view)}   # {note}\n")


def make_link(folder: str | Path, target: str | Path, force: bool = False) -> Path:
    """A symbolic link ``folder/data/<name of target>`` to ``target`` (made absolute);
    returns the link. One there already to the same place is kept; one elsewhere, or a
    file, raises ``FileExistsError`` unless ``force`` (a link is replaced, a file never)."""
    target = Path(target).expanduser().resolve()
    if not target.exists():
        raise FileNotFoundError(target)
    link = Path(folder) / "data" / target.name
    if link.is_symlink():
        if link.resolve() == target:
            return link
        if not force:
            raise FileExistsError(f"{link} links to {link.readlink()}, not {target} "
                                  "(use --force to replace the link)")
        link.unlink()
    elif link.exists():
        raise FileExistsError(f"{link} exists and is not a link; FlowReel never replaces "
                              "data, so move it or link under another name")
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=target.is_dir())
    return link


def make_project(folder: str | Path, source=None, step: int | None = None, *,
                 label: str | None = None, force: bool = False,
                 link: str | Path | None = None, film_name: str | None = None) -> Made:
    """Lay out the project ``folder`` (see the module): its folders, ``flowreel.yml``
    (:func:`init_project`, which ``force`` overwrites), a ``film.yml`` from the film
    template (one shot, ``film_name`` or the folder's name), ``cameras.yml``
    (:func:`cameras_text`), the ``.gitignore`` and, with ``link``, the data link
    (:func:`make_link`). ``film.yml`` and ``cameras.yml`` are written only when
    missing. Returns what was done as :class:`Made`."""
    from flowreel.film.template import template as film_template
    root = Path(folder)
    done = Made(root)
    if (root / PROJECT_FILE).exists() and not force:
        raise FileExistsError(f"{root / PROJECT_FILE} exists (use --force to overwrite it; "
                              "film.yml and cameras.yml are kept either way)")
    for name in FOLDERS:
        sub = root / name
        (done.kept if sub.is_dir() else done.wrote).append(sub)
        sub.mkdir(parents=True, exist_ok=True)
    if link is not None:
        done.link = make_link(root, link, force)
    done.wrote.append(init_project(root, source, step, label=label, force=force))
    name = film_name or root.resolve().name or "my_film"
    for file, text in ((FILM_FILE, lambda: film_template(_shot_name(name))),
                       (CAMERAS_FILE, lambda: cameras_text(source, label))):
        path = root / file
        if path.exists():
            done.kept.append(path)
        else:
            path.write_text(text())
            done.wrote.append(path)
    ignore = root / ".gitignore"
    old = ignore.read_text() if ignore.exists() else ""
    new = gitignore_text(old)
    if new != old:
        ignore.write_text(new)
        done.wrote.append(ignore)
    else:
        done.kept.append(ignore)
    return done


def _shot_name(name: str) -> str:
    """``name`` as a shot name: letters, digits and ``_``."""
    out = "".join(c if c.isalnum() or c == "_" else "_" for c in name).strip("_")
    return out or "my_shot"
