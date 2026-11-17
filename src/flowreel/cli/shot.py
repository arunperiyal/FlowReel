"""``flowreel shot``: render a shot, preview it, measure it, write a template."""
from __future__ import annotations

from shellkit import BaseCommand


class ShotCommand(BaseCommand):
    """The ``shot`` command group."""

    name = "shot"
    description = "Render, preview and measure shots"
    category = "Shots"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description)
        self.actions = p.add_subparsers(dest="shot_cmd", metavar="<action>")
        return p

    def execute(self, args, ctx):
        if not args.shot_cmd:
            ctx.error("give an action: flowreel shot --help")
            return 2
        return getattr(self, "do_" + args.shot_cmd)(args, ctx)
