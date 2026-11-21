"""The ``flowreel`` command (plan Section 13), built on shellkit.

``flowreel shot render reveal.yml -j 8`` runs one command and exits (as a Slurm job
needs); ``flowreel`` alone starts FlowReel's interactive shell, where ``use shot:FILE``
sets the shot that later commands use, ``use view:NAME`` the view of ``camera project``,
and ``use project:DIR`` the project folder, whose
``film.yml`` the film commands use. Commands keep their work in library functions
(``flowreel.scene.render`` ...), so the shell stays a thin layer.
"""
from __future__ import annotations

from pathlib import Path

from shellkit import App, ContextKey

import flowreel


def _shot_file(raw: str, runtime=None) -> str:
    """A shot context value: an existing YAML file, kept as an absolute path."""
    base = Path(getattr(runtime, "cwd", None) or Path.cwd())
    path = (base / raw).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"no such file: {raw}")
    return str(path)


def _project_folder(raw: str, runtime=None) -> str:
    """A project context value: a folder holding ``flowreel.yml`` or ``film.yml``, kept
    as an absolute path."""
    base = Path(getattr(runtime, "cwd", None) or Path.cwd())
    path = (base / raw).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"no such folder: {raw}")
    if not any((path / name).is_file() for name in PROJECT_FILES):
        raise ValueError(f"{raw} is not a project: it has no {' or '.join(PROJECT_FILES)}")
    return str(path)


def _view_name(raw: str, runtime=None) -> str:
    """A view context value: a view's name in cameras.yml (checked when it is used)."""
    name = raw.strip()
    if not name:
        raise ValueError("a view needs a name, as in use view:main")
    return name


#: Files that make a folder a project, for ``use project:DIR``.
PROJECT_FILES = ("flowreel.yml", "film.yml")

CONTEXTS = [
    ContextKey("project", parse=_project_folder, path=True, label="project",
               style="#50a0e0 bold", description="Project folder; film commands use its film.yml",
               format=lambda v: Path(v).name),
    ContextKey("shot", parse=_shot_file, path=True, label="shot", style="#e0a030 bold",
               description="Shot file that shot commands use", format=lambda v: Path(v).name),
    ContextKey("view", parse=_view_name, label="view", style="#70c070 bold",
               description="View of cameras.yml that camera project uses"),
]


def make_app(storage=None) -> App:
    """The FlowReel shellkit app with every command registered. ``storage`` is where the
    shell keeps history and settings (default ``~/.flowreel``)."""
    from flowreel.cli.camera import CameraCommand
    from flowreel.cli.compose import ComposeCommand
    from flowreel.cli.film import FilmCommand
    from flowreel.cli.jobs import JobsCommand
    from flowreel.cli.project import ProjectCommand
    from flowreel.cli.shot import ShotCommand
    app = App("flowreel", version=flowreel.__version__, storage=storage,
              description="Films of flow simulations from configuration files",
              contexts=CONTEXTS, builtins=("core", "files"),
              banner="[bold]flowreel[/bold] " + flowreel.__version__
                     + " [dim]help, Tab, exit[/dim]\n")
    app.register(ProjectCommand)
    app.register(ShotCommand)
    app.register(CameraCommand)
    app.register(ComposeCommand)
    app.register(FilmCommand)
    app.register(JobsCommand)
    return app


def main(argv=None) -> int:
    """Entry point of the ``flowreel`` script."""
    return make_app().run(argv)

