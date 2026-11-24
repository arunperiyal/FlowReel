"""``flowreel project init``: a project folder with its first files.

:func:`make_project` lays out the folder (plan Section 23, question 6): the folders
written by hand (:data:`~flowreel.project.paths.FOLDERS`), ``flowreel.yml``, ``film.yml``
and ``cameras.yml`` at the root, and a ``.gitignore`` for what is generated and for the
data. A case comes in as a tag with ``flowreel data import`` (or ``project init --import``):
data is linked and never copied, since it is large and belongs to the simulation, not the
film. Files a person may have edited (``film.yml``, ``cameras.yml``) are never overwritten.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.project.paths import CAMERAS_FILE, FILM_FILE, FOLDERS, IGNORED, PROJECT_FILE

PROJECT_TEXT = """# flowreel.yml: what belongs to the whole project. Reference: docs/guide/projects/project.md.
# Each case is a tag, data/<tag>/domain.yml, made by `flowreel data import`; its bodies,
# units and series are written there (docs/guide/projects/data.md).
# tags: [bare]                 # the tags the project lists (optional: data/ is read too)
# defaults:
#   backend: osmesa            # the off-screen back end of every command
"""


def init_project(folder: str | Path, *, force: bool = False) -> Path:
    """Write ``folder/flowreel.yml`` (only comments to fill in); returns its path. Raises
    ``FileExistsError`` unless ``force``."""
    path = Path(folder) / PROJECT_FILE
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists (use --force to overwrite)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROJECT_TEXT)
    return path


@dataclass
class Made:
    """What :func:`make_project` did: the project ``root``, and the files and folders it
    ``wrote`` and those it ``kept`` as they were."""

    root: Path
    wrote: list[Path] = field(default_factory=list)
    kept: list[Path] = field(default_factory=list)


def gitignore_text(old: str = "") -> str:
    """``old`` (a ``.gitignore``'s text) with the lines of
    :data:`~flowreel.project.paths.IGNORED` it lacks added at the end."""
    have = {line.strip() for line in old.splitlines()}
    missing = [line for line in IGNORED if line not in have and line.rstrip("/") not in have]
    if not missing:
        return old
    head = "" if not old else old if old.endswith("\n") else old + "\n"
    return head + "# Made by FlowReel (docs/guide/projects/project.md): generated output and linked data\n" \
        + "\n".join(missing) + "\n"


def cameras_text(source=None, label: str | None = None) -> str:
    """A first ``cameras.yml``: one view ``main`` looking down -z with the source's
    domain filling a 16:9 picture, the shape of a shot's default size (a placeholder
    without a source), to replace with one picked in ``flowreel camera edit``."""
    from flowreel.scene.camera_file import view_line
    from flowreel.scene.views import View
    view = View((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0), name="main")
    note = "a placeholder: no case was given"
    if source is not None:
        from flowreel.scene.framing import fit
        view = fit(view, source.bounds(), margin=1.05, aspect=16 / 9)
        note = f"the whole domain of {label or getattr(source, 'name', 'the source')}, from +z"
    return ("# cameras.yml written by `flowreel project init`: every shot and caption of\n"
            "# the project reads its views and tracks here. Reference: docs/guide/shots/cameras.md;\n"
            "# pick views and tracks with `flowreel camera edit`.\n"
            f"views:\n  - {view_line(view)}   # {note}\n")


def make_project(folder: str | Path, *, force: bool = False, film_name: str | None = None) -> Made:
    """Lay out the project ``folder`` (see the module): its folders, ``flowreel.yml``
    (:func:`init_project`, which ``force`` overwrites), a ``film.yml`` from the film
    template (one scene, ``film_name`` or the folder's name), ``cameras.yml``
    (:func:`cameras_text`) and the ``.gitignore``. ``film.yml`` and ``cameras.yml`` are
    written only when missing. Returns what was done as :class:`Made`."""
    from flowreel.film.scene_template import film_template
    root = Path(folder)
    done = Made(root)
    if (root / PROJECT_FILE).exists() and not force:
        raise FileExistsError(f"{root / PROJECT_FILE} exists (use --force to overwrite it; "
                              "film.yml and cameras.yml are kept either way)")
    for name in FOLDERS:
        sub = root / name
        (done.kept if sub.is_dir() else done.wrote).append(sub)
        sub.mkdir(parents=True, exist_ok=True)
    done.wrote.append(init_project(root, force=force))
    name = film_name or root.resolve().name or "my_film"
    for file, text in ((FILM_FILE, lambda: film_template(_shot_name(name))),
                       (CAMERAS_FILE, cameras_text)):
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
