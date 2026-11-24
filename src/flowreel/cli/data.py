"""``flowreel data``: a project's data by tag (plan Section 19.10, Phase 9).

``data import`` brings a case in as a tag (:mod:`flowreel.project.imports`); ``list``,
``info``, ``remove``, ``rename`` and ``check`` look after the tags; ``template`` prints a
``domain.yml`` with every key. ``import history`` and ``extract`` come with Phase 9's next
branches.
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from shellkit import BaseCommand, CommandError

EXAMPLES = {
    "data": """examples:
  flowreel data import plt --path /scratch/run/binary --tag bare
  flowreel data list
  flowreel data info bare
  flowreel data template                    domain.yml of a PLT case, every key

Reference: docs/guide/projects/data.md and docs/guide/commands.md.""",
    "import": """examples:
  flowreel data import plt --path /scratch/run/binary --tag bare
                                            link the folder of PLT files as data/bare/plt
  flowreel data import vtk --path runs/cyl35 --tag cyl35 --body cylinder=runs/cyl35/cylinder.vtp
  flowreel data import plt --path small_case --tag test --copy
                                            copy instead of link (asks --yes above 5 GB)
  flowreel data import geometry --name grooved_cylinder --tag carve --param grooves=4
  flowreel data import plt --path /scratch/run2/binary --tag bare --force
                                            point bare at another folder; edits kept""",
    "list": """examples:
  flowreel data list""",
    "info": """examples:
  flowreel data info bare                   a tag of this project
  flowreel data info /scratch/run/binary    any folder of PLT or VTK files, no project needed""",
    "remove": """examples:
  flowreel data remove test                 the links and domain.yml; never the case""",
    "rename": """examples:
  flowreel data rename bare smooth          the folder, and every file that names it""",
    "check": """examples:
  flowreel data check                       every tag: links, sources, units, series
  flowreel data check bare""",
    "template": """examples:
  flowreel data template                    a PLT case
  flowreel data template --kind geometry    a body made in code
  flowreel data template --kind vtk -o data/run/domain.yml""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


class DataCommand(BaseCommand):
    """The ``data`` command group."""

    name = "data"
    description = "A project's data by tag: each case's domain.yml"
    category = "Projects"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["data"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="data_cmd", metavar="<action>")
        i = _parser(actions, "import", help="bring a case in as a tag (a link; --copy copies)",
                    description="Link the folder a case's files are in under data/TAG/ (plt or "
                                "vtk; geometry links nothing) and write data/TAG/domain.yml with "
                                "what was measured: the reader's options, each wall zone as a "
                                "body with its axis and diameter, and the steps, zones, fields "
                                "and bounds; the units are left to fill in. --copy copies the "
                                "files instead, after saying their size. A tag holding a case "
                                "already is refused unless --force, which replaces the link and "
                                "keeps the edits of domain.yml.")
        i.add_argument("kind", choices=("plt", "vtk", "geometry"), help="what the case is")
        i.add_argument("--path", metavar="PATH", help="the folder the files are in")
        i.add_argument("--tag", required=True, metavar="TAG",
                       help="the tag: letters, digits, - and _")
        i.add_argument("--body", action="append", metavar="NAME=FILE",
                       help="vtk: a body's surface file, by name (repeat for each)")
        i.add_argument("--flow", metavar="FILE",
                       help="vtk: the flow within PATH (default its one .pvd)")
        i.add_argument("--name", metavar="FUNCTION", help="geometry: the body made in code")
        i.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                       help="geometry: a parameter of the body (repeat)")
        i.add_argument("--copy", action="store_true", help="copy the files instead of linking")
        i.add_argument("--yes", action="store_true", help="copy even above 5 GB")
        i.add_argument("--force", action="store_true",
                       help="replace the tag's link (domain.yml keeps its edits)")

        _parser(actions, "list", help="the project's tags: kind, steps, size, link",
                description="List every tag under data/: its kind, its steps, its size, "
                            "and where its link points (or that it does not resolve).")
        n = _parser(actions, "info", help="what a tag (or any case folder) is",
                    description="Describe a tag of the project, or any folder of PLT or VTK "
                                "files (no project needed): steps and times, zones, fields, "
                                "bounds, and, for a tag, its units and bodies.")
        n.add_argument("what", metavar="TAG|PATH", help="a tag, or a folder of files")
        r = _parser(actions, "remove", help="remove a tag (never the case)",
                    description="Remove data/TAG/: its links (not what they point at), its "
                                "domain.yml and the series FlowReel wrote there. A tag whose "
                                "files were copied asks for --yes.")
        r.add_argument("tag", metavar="TAG")
        r.add_argument("--yes", action="store_true", help="remove copied files too")
        m = _parser(actions, "rename", help="rename a tag and every file that names it",
                    description="Rename data/OLD/ to data/NEW/, and every file of the project "
                                "that names it: source: and tag: values, OLD.body names, and "
                                "the tags: list of flowreel.yml.")
        m.add_argument("old", metavar="OLD")
        m.add_argument("new", metavar="NEW")
        c = _parser(actions, "check", help="check the tags: links, sources, units, series",
                    description="For every tag (or the ones given): its link resolves, its "
                                "source opens, its units are given, and its series files exist. "
                                "Exit status 1 when something is wrong.")
        c.add_argument("tags", nargs="*", metavar="TAG")

        t = _parser(actions, "template", help="a tag's domain.yml with every key",
                    description="Print (or write with -o) a domain.yml with every key, at "
                                "its default or as an example, each with a comment: what a "
                                "case under data/<tag>/ can say about itself.")
        t.add_argument("--kind", choices=("plt", "vtk", "geometry"), default="plt",
                       help="the kind of case (default plt)")
        t.add_argument("-o", "--output", metavar="FILE", help="write it here instead")
        t.add_argument("--force", action="store_true", help="overwrite FILE")
        return p

    def execute(self, args, ctx):
        from flowreel.project.imports import DataError
        from flowreel.scene.errors import ConfigError
        if not args.data_cmd:
            ctx.error("give an action: flowreel data --help")
            return 2
        try:
            return getattr(self, "do_" + args.data_cmd)(args, ctx)
        except (DataError, ConfigError) as exc:
            raise CommandError(str(exc)) from None

    def _root(self, ctx):
        from flowreel.cli.project import project_root
        return project_root(ctx)

    def do_import(self, args, ctx):
        from flowreel.project.imports import human, import_data
        bodies = _pairs(args.body, "--body", number=False) if args.body else None
        params = _pairs(args.param, "--param", number=True)
        if args.kind != "geometry" and (args.name or params):
            raise CommandError("--name and --param are for a geometry tag")
        if args.kind != "vtk" and (bodies or args.flow):
            raise CommandError("--body and --flow are for a vtk tag")
        done = import_data(self._root(ctx), args.kind, args.path, args.tag, bodies=bodies,
                           flow=args.flow, function=args.name, params=params, copy=args.copy,
                           yes=args.yes, force=args.force, say=ctx.out)
        for link in done.linked:
            ctx.out(f"linked {link} -> {Path(link).readlink()}")
        for target in done.copied:
            ctx.out(f"copied {human(done.nbytes)} into {target}")
        verb = "updated" if done.updated else "wrote"
        ctx.out(f"{verb} {done.domain}: fill in the units (docs/guide/projects/data.md#units)")
        return 0

    def do_list(self, args, ctx):
        from flowreel.project.imports import human, state, tags
        root = self._root(ctx)
        names = tags(root)
        if not names:
            ctx.out("no tags under data/ (data import brings a case in)")
            return 0
        for name in names:
            s = state(root, name)
            steps = f"{s.steps[2]} steps, {s.steps[0]} to {s.steps[1]}" if s.steps else "steps ?"
            where = "" if s.kind == "geometry" else (
                f" -> {s.target}" if s.resolves else f" -> {s.target or 'missing'} (does not resolve)")
            size = f", {human(s.nbytes)}" if s.nbytes else ""
            ctx.out(f"{name:<12} {s.kind or '?':<8} {steps}{size}{where}")
        return 0

    def do_info(self, args, ctx):
        from flowreel.project.domain import DOMAIN_FILE, load_domain
        from flowreel.project.imports import describe
        from flowreel.project.paths import find_root
        root = find_root(Path.cwd()) if not ctx.get("project") else Path(ctx.get("project"))
        folder = None if root is None else root / "data" / args.what
        if folder is not None and (folder / DOMAIN_FILE).is_file():
            lines = describe(load_domain(folder))
        elif Path(args.what).expanduser().is_dir():
            lines = describe(args.what)
        else:
            raise CommandError(f"{args.what!r} is neither a tag of this project nor a folder")
        for line in lines:
            ctx.out(line)
        return 0

    def do_remove(self, args, ctx):
        from flowreel.project.imports import remove, state
        root = self._root(ctx)
        s = state(root, args.tag)
        if s.target == "(copied)" and not args.yes:
            raise CommandError(f"tag {args.tag!r} holds copied files; add --yes to remove them")
        removed = remove(root, args.tag)
        ctx.out(f"removed data/{args.tag}/ ({', '.join(removed)}); the case itself is untouched")
        return 0

    def do_rename(self, args, ctx):
        from flowreel.project.imports import rename
        root = self._root(ctx)
        changed = rename(root, args.old, args.new)
        ctx.out(f"renamed data/{args.old}/ to data/{args.new}/"
                + (f"; changed {', '.join(str(p.relative_to(root)) for p in changed)}"
                   if changed else ""))
        return 0

    def do_check(self, args, ctx):
        from flowreel.project.imports import state, tags
        root = self._root(ctx)
        names = args.tags or tags(root)
        bad = 0
        for name in names:
            s = state(root, name, deep=True)
            if s.problems:
                bad += 1
                for p in s.problems:
                    ctx.out(f"{name}: {p}")
            else:
                steps = f", {s.steps[2]} steps" if s.steps else ""
                ctx.out(f"{name}: ok{steps}")
        return 1 if bad else 0

    def do_template(self, args, ctx):
        from flowreel.project.domain import template
        text = template(args.kind)
        if not args.output:
            ctx.out(text, end="")
            return 0
        path = Path(args.output)
        if path.exists() and not args.force:
            raise CommandError(f"{path} exists (use --force to overwrite)")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        ctx.out(f"wrote {path}")
        return 0


def _pairs(items, flag: str, number: bool) -> dict:
    """``NAME=VALUE`` items as a mapping (values as numbers with ``number``)."""
    out = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise CommandError(f"{flag} expects NAME=VALUE, got {item!r}")
        if number:
            try:
                value = float(value) if "." in value or "e" in value.lower() else int(value)
            except ValueError:
                pass
        out[key.strip()] = value
    return out
