"""``flowreel project``: make a project folder, and the project rules the other commands
follow.

``project init`` is a thin layer over :func:`flowreel.project.init.make_project`.
:func:`project_root` is how every command that works on a project's files finds it
(walking up from the file it was given, the shell's ``use project:DIR`` or the current
folder) and stops outside one, saying how to make one (plan Section 23, question 6).
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from shellkit import BaseCommand, CommandError

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "project": """examples:
  flowreel project init plt:bare/BR0SG0U1P0
  flowreel project init vtk:run/flow.pvd --body run/body_*.vtp -o films/afms
  flowreel project init -o films/afms --link /scratch/afms/run

Reference: docs/project.md, docs/bodies.md and docs/commands.md.""",
    "init": """examples:
  flowreel project init plt:bare/BR0SG0U1P0          one body per surface zone
  flowreel project init vtk:flow.pvd --body body.vtp --step 5000
  flowreel project init vtk:flow.pvd --body cylinder=wall.vtp
                                                    the body named cylinder
  flowreel project init geometry:grooved_cylinder -o carve --force
  flowreel project init --link /scratch/run vtk:data/run/flow.pvd
                                                    link the data first, read it there
  flowreel project init                             the folders only; bodies by hand""",
    "info": """examples:
  flowreel project info                             the project of this folder
  flowreel project info films/afms""",
    "clean": """examples:
  flowreel project clean                            the caches (.flowreel/cache/)
  flowreel project clean --frames --dry-run         what removing the frames would free
  flowreel project clean --frames --clips           frames and finished clips""",
}


def project_root(ctx, *files) -> Path:
    """The root of the project a command works in: the one holding the first of
    ``files`` given (the shot, layout or film file), else the shell's ``use project:DIR``,
    else the current folder. Raises ``CommandError`` outside a project, saying how to make
    one."""
    from flowreel.project.paths import NotInProject, require_root
    start = next((f for f in files if f), None)
    if start is None:
        start = ctx.get("project") if hasattr(ctx, "get") else None
    try:
        return require_root(start)
    except NotInProject as exc:
        raise CommandError(str(exc)) from None


def default_out(ctx, out, *files, kind: str = "frames") -> Path:
    """``-o``'s folder when given, else ``<project root>/<kind>`` (:func:`project_root`)."""
    return Path(out) if out else project_root(ctx, *files) / kind


def body_option(values) -> str | dict | None:
    """``--body`` as the source takes it: one ``FILE`` (a body named ``body``), or
    ``NAME=FILE`` once or more (bodies named as given). Raises ``CommandError`` on a mix,
    a repeated name or an empty part."""
    if not values:
        return None
    named = [v for v in values if "=" in v]
    if not named:
        if len(values) > 1:
            raise CommandError("several --body files need a name each: --body NAME=FILE")
        return values[0]
    if len(named) != len(values):
        raise CommandError("give every --body as NAME=FILE, or one FILE alone")
    bodies = {}
    for value in values:
        name, _, path = value.partition("=")
        if not name or not path:
            raise CommandError(f"--body {value!r}: expected NAME=FILE")
        if name in bodies:
            raise CommandError(f"--body: the name {name!r} is given twice")
        bodies[name] = path
    return bodies


def open_source(text: str, body: str | dict | None = None):
    """The source written ``adapter:location`` on the command line (``geometry:NAME``
    names a body; others take the location as ``path``), with ``body`` for an adapter
    that reads the body from its own file: a file or pattern (the body ``body``), or a
    mapping ``{name: file}`` (see :func:`body_option`)."""
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
    description = "Make a project folder, see what it holds, clean what it made"
    category = "Projects"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["project"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="project_cmd", metavar="<action>")
        i = actions.add_parser(
            "init", help="make a project folder, with a body per surface zone",
            description="\n\n".join(textwrap.fill(s, 78) for s in (
                "Make the project folder DIR: shots/, text/, cards/, assets/ and data/, "
                "film.yml and cameras.yml at the root (kept if they exist), a .gitignore "
                "for frames/, clips/, .flowreel/ and data/, and flowreel.yml declaring "
                "every surface zone of SOURCE as a body, with its axis and diameter "
                "measured from the surface. Supports and series are written commented "
                "out, to fill in. Without SOURCE, flowreel.yml has only comments.",
                "--link puts a symbolic link to the data in data/ (data is never copied), "
                "before SOURCE is read, so SOURCE can name it there.")),
            epilog=EXAMPLES["init"], formatter_class=argparse.RawDescriptionHelpFormatter)
        i.add_argument("source", metavar="SOURCE", nargs="?",
                       help="adapter:location, e.g. plt:CASE or vtk:FILE (optional)")
        i.add_argument("--body", metavar="[NAME=]FILE", action="append",
                       help="body file or pattern, for a source that reads it separately "
                            "(vtk); NAME=FILE names the body (default 'body'), and may be "
                            "given once per body")
        i.add_argument("--step", type=int, metavar="N", help="step to measure (default the first)")
        i.add_argument("-o", "--out", default=".", metavar="DIR",
                       help="project folder (default the current one)")
        i.add_argument("--link", metavar="PATH",
                       help="link PATH (a case folder or file) into DIR/data/ under its name")
        i.add_argument("--force", action="store_true",
                       help="overwrite flowreel.yml (and replace a data link) if it exists")

        n = actions.add_parser(
            "info", help="what the project holds, and the size of what it made",
            description=textwrap.fill(
                "Print the project's data links, the sources its shots read, the bodies "
                "of flowreel.yml, every shot file with the frames drawn for it, the views "
                "and tracks of cameras.yml, the film's shots and planned length, and the "
                "size of frames/, clips/ and .flowreel/. Files that do not load are "
                "listed with their error. Nothing is changed.", 78),
            epilog=EXAMPLES["info"], formatter_class=argparse.RawDescriptionHelpFormatter)
        n.add_argument("folder", nargs="?", metavar="DIR",
                       help="a folder in the project (default: use project:DIR, else here)")

        c = actions.add_parser(
            "clean", help="remove caches, frames or clips the project made",
            description=textwrap.fill(
                "Remove generated output of the project: --cache (.flowreel/cache/, the "
                "default when nothing is named), --frames (frames/) and --clips (clips/). "
                "Files written by hand, the data, and the measured frame costs and job "
                "records in .flowreel/ are never removed. A folder that is a link is "
                "skipped.", 78),
            epilog=EXAMPLES["clean"], formatter_class=argparse.RawDescriptionHelpFormatter)
        c.add_argument("folder", nargs="?", metavar="DIR",
                       help="a folder in the project (default: use project:DIR, else here)")
        c.add_argument("--cache", action="store_true", help="the caches, .flowreel/cache/")
        c.add_argument("--frames", action="store_true", help="every frame folder, frames/")
        c.add_argument("--clips", action="store_true", help="the finished clips, clips/")
        c.add_argument("--dry-run", action="store_true",
                       help="say what would be removed, and its size; remove nothing")
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

    def do_info(self, args, ctx):
        from flowreel.project.info import info
        ctx.out(info(project_root(ctx, args.folder)).text())
        return 0

    def do_clean(self, args, ctx):
        from flowreel.project.info import clean, human
        root = project_root(ctx, args.folder)
        what = [w for w in ("cache", "frames", "clips") if getattr(args, w)] or ["cache"]
        done = clean(root, what, dry_run=args.dry_run)
        verb = "would remove" if args.dry_run else "removed"
        for path, n in done.removed:
            ctx.out(f"{verb} {path.relative_to(root)}/ ({human(n)})")
        for path in done.skipped:
            ctx.warn(f"skipped {path.relative_to(root)}: a link (clean what it points to by hand)")
        if not done.removed and not done.skipped:
            ctx.out(f"nothing to remove ({', '.join(what)})")
        elif done.removed:
            ctx.out(f"{verb} {human(done.total)} in all")
        return 0

    def do_init(self, args, ctx):
        from flowreel.project.init import make_link, make_project
        from flowreel.project.paths import PROJECT_FILE
        folder = Path(args.out)
        if (folder / PROJECT_FILE).exists() and not args.force:
            raise CommandError(f"{folder / PROJECT_FILE} exists (use --force to overwrite it; "
                               "film.yml and cameras.yml are kept either way)")
        if args.source is None and (args.body or args.step is not None):
            raise CommandError("--body and --step need a SOURCE")
        try:
            if args.link:                     # first, so that SOURCE may read the data there
                link = make_link(folder, args.link, args.force)
                ctx.out(f"linked {link} -> {link.readlink()}")
            source = None
            if args.source is not None:
                source = open_source(args.source, body_option(args.body))
                if args.step is not None and args.step not in source.steps():
                    raise CommandError(f"step {args.step} is not saved (steps "
                                       f"{source.steps()[0]} to {source.steps()[-1]})")
            made = make_project(folder, source, args.step, label=args.source, force=args.force)
        except (FileExistsError, LookupError, ValueError) as exc:
            raise CommandError(str(exc)) from None
        made_dirs = [p.name + "/" for p in made.wrote if p.is_dir()]
        if made_dirs:
            ctx.out(f"made {folder}: {' '.join(made_dirs)}")
        for verb, paths in (("wrote", made.wrote), ("kept", made.kept)):
            files = [str(p) for p in paths if p.is_file() and p.name != PROJECT_FILE]
            if files:
                ctx.out(f"{verb} {', '.join(files)}")
        path = folder / PROJECT_FILE
        if source is None:
            ctx.out(f"wrote {path} without bodies: declare them, or run project init SOURCE "
                    f"--force")
        else:
            names = source.bodies()
            ctx.out(f"wrote {path}: {len(names)} {'body' if len(names) == 1 else 'bodies'} "
                    f"({', '.join(names)}); fill in the supports")
        return 0
