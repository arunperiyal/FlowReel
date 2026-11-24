"""``flowreel panel``: a panel's frames drawn, and a panel file to start from.

``panel draw`` draws a panel's own frames (as ``compose panel`` did, which stays until
the film of shots goes); in a film of scenes a panel box is drawn by the build instead,
at the box's size. ``panel template`` writes a commented panel file of a type.
"""
from __future__ import annotations

import argparse
import textwrap
import time
from pathlib import Path

from shellkit import BaseCommand, CommandError, paths

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "panel": """examples:
  flowreel panel draw panels/lift.yml -j 4
  flowreel panel template --type map -o panels/liftmap.yml

Reference: docs/guide/shots/panels.md and docs/guide/commands.md.""",
    "draw": """examples:
  flowreel panel draw panels/lift.yml              every frame, into frames/lift/
  flowreel panel draw panels/lift.yml -j 8         eight runs of frames at once
  flowreel panel draw panels/lift.yml --frames 0:10 --force""",
    "template": """examples:
  flowreel panel template                          a series panel
  flowreel panel template --type section -o panels/wake_section.yml""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


class PanelCommand(BaseCommand):
    """The ``panel`` command group."""

    name = "panel"
    description = "Draw a panel's frames, or start a panel file"
    category = "Compose"

    def setup_parser(self, subparsers):
        from flowreel.cli.compose import _common
        from flowreel.compose.panel_template import TYPES
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["panel"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="panel_cmd", metavar="<action>")
        d = _parser(actions, "draw", help="draw a panel's frames",
                    description="Draw the frames of a panel file into OUT/<panel>/"
                                "frame_00000.png, frame i at the panel's time i. Frames whose "
                                "key did not change are skipped. With -j N the frames are cut "
                                "into N runs of consecutive frames, each drawn by its own "
                                "process. A panel box of a film of scenes needs no draw: the "
                                "build draws it at the box's size.")
        d.add_argument("panel", help="the panel file").completer = paths((".yml", ".yaml"))
        _common(d, "frames")
        t = _parser(actions, "template", help="a commented panel file of a type",
                    description="Print (or write with -o) a panel file of a type: a working "
                                "example for a project of tags, with the type's other keys "
                                "commented.")
        t.add_argument("--type", choices=TYPES, default="series",
                       help="the panel's type (default series)")
        t.add_argument("-o", "--output", metavar="FILE", help="write it here instead")
        t.add_argument("--force", action="store_true", help="overwrite FILE")
        return p

    def execute(self, args, ctx):
        if not args.panel_cmd:
            ctx.error("give an action: flowreel panel --help")
            return 2
        try:
            return getattr(self, "do_" + args.panel_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename}") from None
        except (ValueError, LookupError) as exc:
            raise CommandError(str(exc.args[0]) if isinstance(exc, LookupError) and exc.args
                               else str(exc)) from None

    def do_draw(self, args, ctx):
        from flowreel.cli.compose import _as_job
        from flowreel.cli.jobs import run_single, slurm_wanted
        from flowreel.cli.project import project_root
        from flowreel.cli.shot import parse_frames
        from flowreel.compose import panel
        if args.jobs < 1:
            raise CommandError("-j must be at least 1")
        root = project_root(ctx, args.panel)
        if args.out is None:
            args.out = str(root / "frames")
        if slurm_wanted(args):
            cmd = _as_job(args, "panel", args.panel, [])
            cmd[1:3] = ["panel", "draw"]
            return run_single(ctx, Path(args.panel).stem, cmd, "compose", args)
        frames = parse_frames(args.frames) if args.frames else None
        start = time.perf_counter()
        report = panel(args.panel, args.out, frames=frames, jobs=args.jobs, force=args.force,
                       progress=lambda e: ctx.out(f"  {e[1].name} {e[2]}"))
        ctx.out(f"{report.count('drawn')} drawn, {report.count('skipped')} skipped in "
                f"{time.perf_counter() - start:.1f} s -> {report.folder}")
        return 0

    def do_template(self, args, ctx):
        from flowreel.compose.panel_template import template
        text = template(args.type)
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
