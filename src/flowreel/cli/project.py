"""``flowreel project``: set up a project's ``flowreel.yml``.

A thin layer over :func:`flowreel.project.init.init_project`.
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from shellkit import BaseCommand, CommandError

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "project": """examples:
  flowreel project init flexflow:bare/BR0SG0U1P0
  flowreel project init vtk:run/flow.pvd --body run/body_*.vtp -o films/afms

Reference: docs/bodies.md and docs/commands.md.""",
    "init": """examples:
  flowreel project init flexflow:bare/BR0SG0U1P0     one body per surface zone
  flowreel project init vtk:flow.pvd --body body.vtp --step 5000
  flowreel project init geometry:grooved_cylinder -o carve --force""",
}


def open_source(text: str, body: str | None = None):
    """The source written ``adapter:location`` on the command line (``geometry:NAME``
    names a body; others take the location as ``path``), with ``body`` for an adapter
    that reads the body from its own file."""
    from flowreel import sources
    adapter, sep, location = text.partition(":")
    if not sep or not adapter or not location:
        raise CommandError(f"expected SOURCE as adapter:location (for example "
                           f"vtk:flow.pvd), got {text!r}")
    options = {"body": location} if adapter == "geometry" else {"path": location}
    if body is not None:
        if adapter == "geometry":
            raise CommandError("--body is for sources that read a body file, not geometry")
        options["body"] = body
    try:
        return sources.create(adapter, **options)
    except KeyError as exc:
        raise CommandError(str(exc.args[0]) if exc.args else str(exc)) from None


class ProjectCommand(BaseCommand):
    """The ``project`` command group."""

    name = "project"
    description = "Set up a project: flowreel.yml and its bodies"
    category = "Projects"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["project"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="project_cmd", metavar="<action>")
        i = actions.add_parser(
            "init", help="write flowreel.yml with a body per surface zone",
            description=textwrap.fill(
                "Write DIR/flowreel.yml declaring every surface zone of SOURCE as a body, "
                "with its axis and diameter measured from the surface. Supports and series "
                "are written commented out, to fill in.", 78),
            epilog=EXAMPLES["init"], formatter_class=argparse.RawDescriptionHelpFormatter)
        i.add_argument("source", metavar="SOURCE", help="adapter:location, e.g. flexflow:CASE")
        i.add_argument("--body", metavar="FILE",
                       help="body file or pattern, for a source that reads it separately (vtk)")
        i.add_argument("--step", type=int, metavar="N", help="step to measure (default the first)")
        i.add_argument("-o", "--out", default=".", metavar="DIR",
                       help="project folder (default the current one)")
        i.add_argument("--force", action="store_true", help="overwrite flowreel.yml if it exists")
        return p

    def execute(self, args, ctx):
        if not args.project_cmd:
            ctx.error("give an action: flowreel project --help")
            return 2
        try:
            return getattr(self, "do_" + args.project_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename or exc}") from None

    def do_init(self, args, ctx):
        from flowreel.project.init import init_project
        source = open_source(args.source, args.body)
        if args.step is not None and args.step not in source.steps():
            raise CommandError(f"step {args.step} is not saved (steps {source.steps()[0]} to "
                               f"{source.steps()[-1]})")
        try:
            path = init_project(Path(args.out), source, args.step, label=args.source,
                                force=args.force)
        except (FileExistsError, LookupError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        names = source.bodies()
        ctx.out(f"wrote {path}: {len(names)} {'body' if len(names) == 1 else 'bodies'} "
                f"({', '.join(names)}); fill in the supports")
        return 0
