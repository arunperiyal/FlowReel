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
  flowreel project init -o films/afms
  flowreel project init --import plt:/scratch/run/binary --tag bare

Reference: docs/guide/projects/project.md and docs/guide/commands.md.""",
    "init": """examples:
  flowreel project init                             the folders and first files, here
  flowreel project init -o carve --force            overwrite flowreel.yml
  flowreel project init --import plt:/scratch/run/binary --tag bare
                                                    the folders, and the case as a tag
  flowreel project init --import vtk:/scratch/run --tag run -o films/afms""",
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


def _import_into(folder: Path, spec: str, tag: str, made, ctx) -> None:
    """``project init --import KIND:PATH --tag TAG``: import the case, then fit the first
    view of a cameras.yml written just now to it."""
    from flowreel.project.domain import load_domain, open_tag
    from flowreel.project.imports import import_data
    from flowreel.project.init import cameras_text
    from flowreel.project.paths import CAMERAS_FILE
    kind, sep, path = spec.partition(":")
    if not sep or kind not in ("plt", "vtk"):
        raise CommandError(f"--import expects plt:PATH or vtk:PATH, got {spec!r}")
    done = import_data(folder, kind, path, tag, say=ctx.out)
    for link in done.linked:
        ctx.out(f"linked {link} -> {Path(link).readlink()}")
    ctx.out(f"wrote {done.domain}: fill in the units")
    cameras = folder / CAMERAS_FILE
    if cameras in made.wrote:
        cameras.write_text(cameras_text(open_tag(load_domain(done.folder)), label=f"tag {tag}"))


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
            "init", help="make a project folder",
            description="\n\n".join(textwrap.fill(s, 78) for s in (
                "Make the project folder DIR: shots/, panels/, layouts/, assets/ and "
                "data/, flowreel.yml, film.yml and cameras.yml at the root (film.yml and "
                "cameras.yml are kept if they exist), and a .gitignore for frames/, "
                "clips/, .flowreel/ and data/.",
                "A case comes in as a tag: --import KIND:PATH --tag TAG does what data "
                "import does, and fits the first view of cameras.yml to the case.")),
            epilog=EXAMPLES["init"], formatter_class=argparse.RawDescriptionHelpFormatter)
        i.add_argument("-o", "--out", default=".", metavar="DIR",
                       help="project folder (default the current one)")
        i.add_argument("--force", action="store_true", help="overwrite flowreel.yml if it exists")
        i.add_argument("--import", dest="import_", metavar="KIND:PATH",
                       help="import a case as a tag as well (plt:PATH, vtk:PATH), as "
                            "data import does; give --tag")
        i.add_argument("--tag", metavar="TAG", help="the tag of --import")

        n = actions.add_parser(
            "info", help="what the project holds, and the size of what it made",
            description=textwrap.fill(
                "Print the project's tags, the sources its shots read, every shot file "
                "with the frames drawn for it, the views and tracks of cameras.yml, the "
                "film's scenes, and the size of frames/, clips/ and .flowreel/. Files that do not load are "
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
        from flowreel.project.init import make_project
        from flowreel.project.paths import PROJECT_FILE
        folder = Path(args.out)
        if (folder / PROJECT_FILE).exists() and not args.force:
            raise CommandError(f"{folder / PROJECT_FILE} exists (use --force to overwrite it; "
                               "film.yml and cameras.yml are kept either way)")
        if bool(args.import_) != bool(args.tag):
            raise CommandError("--import and --tag go together")
        try:
            made = make_project(folder, force=args.force)
            if args.import_:
                _import_into(folder, args.import_, args.tag, made, ctx)
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
        if args.import_:
            ctx.out(f"wrote {path}; the case's bodies and units are in "
                    f"data/{args.tag}/domain.yml")
        else:
            ctx.out(f"wrote {path}; bring a case in with data import")
        return 0
