"""The ``flowreel`` command (plan Section 13), built on shellkit.

``flowreel shot render reveal.yml -j 8`` runs one command and exits (as a Slurm job
needs); ``flowreel`` alone starts FlowReel's interactive shell, where ``use shot:FILE``
sets the shot that later commands use. Commands keep their work in library functions
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


CONTEXTS = [
    ContextKey("shot", parse=_shot_file, path=True, label="shot", style="#e0a030 bold",
               description="Shot file that shot commands use", format=lambda v: Path(v).name),
]


def make_app(storage=None) -> App:
    """The FlowReel shellkit app with every command registered. ``storage`` is where the
    shell keeps history and settings (default ``~/.flowreel``)."""
    from flowreel.cli.project import ProjectCommand
    from flowreel.cli.shot import ShotCommand
    app = App("flowreel", version=flowreel.__version__, storage=storage,
              description="Films of flow simulations from configuration files",
              contexts=CONTEXTS, builtins=("core", "files"),
              banner="[bold]flowreel[/bold] " + flowreel.__version__
                     + " [dim]help, Tab, exit[/dim]\n")
    app.register(ProjectCommand)
    app.register(ShotCommand)
    return app


def main(argv=None) -> int:
    """Entry point of the ``flowreel`` script."""
    return make_app().run(argv)

