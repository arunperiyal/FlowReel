"""``flowreel data``: a project's data by tag (plan Section 19.10, Phase 9).

``data template`` prints a tag's ``domain.yml`` with every key; the other actions
(import, list, info, remove, rename, check, extract) come with Phase 9's next branches.
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from shellkit import BaseCommand, CommandError

EXAMPLES = {
    "data": """examples:
  flowreel data template                    domain.yml of a PLT case, every key
  flowreel data template --kind vtk -o data/run/domain.yml

Reference: docs/guide/projects/data.md and docs/guide/commands.md.""",
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
        if not args.data_cmd:
            ctx.error("give an action: flowreel data --help")
            return 2
        return getattr(self, "do_" + args.data_cmd)(args, ctx)

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
