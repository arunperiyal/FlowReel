"""``flowreel compose``: compose a layout's frames, draw a panel's frames.

Each action is a thin layer over a library function (``flowreel.compose.layout``,
``flowreel.compose.panel``); the work and its checks live there.
"""
from __future__ import annotations

import argparse
import textwrap
import time
from pathlib import Path

from shellkit import BaseCommand, CommandError, paths

from flowreel.cli.shot import parse_frames
from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "compose": """examples:
  flowreel compose panel panels/lift.yml -j 4
  flowreel compose layout compare.yml
  flowreel compose layout compare.yml --scale 0.5

Reference: docs/commands.md.""",
    "layout": """examples:
  flowreel compose layout compare.yml             every frame, into frames/compare/
  flowreel compose layout compare.yml --scale 0.5 a half-size draft, frames/compare@960x540/
  flowreel compose layout compare.yml --frames 0:48:4 -j 8
  flowreel compose layout compare.yml --force     compose again even if nothing changed
  flowreel compose layout compare.yml --submit --after 1310   as a job, after the renders""",
    "panel": """examples:
  flowreel compose panel lift.yml                 every frame, into frames/lift/
  flowreel compose panel lift.yml -j 8            eight runs of frames at once
  flowreel compose panel lift.yml --frames 0:10 --force""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _common(parser, what: str):
    parser.add_argument("--frames", metavar="SPEC",
                        help=f"{what} to draw: A, A:B (both included), A:B:E, or a comma list")
    parser.add_argument("--force", action="store_true",
                        help="draw the frames even when their key did not change")
    parser.add_argument("-j", "--jobs", type=int, default=1, metavar="N",
                        help="processes drawing at once (default 1)")
    parser.add_argument("-o", "--out", default="frames", metavar="DIR",
                        help="folder of the frame folders (default ./frames)")
    from flowreel.cli.jobs import add_slurm_args
    add_slurm_args(parser)


def _as_job(args, what: str, file: str, extra: list[str]) -> list[str]:
    """The ``flowreel compose WHAT FILE ...`` line a job runs: these options, without the
    Slurm ones."""
    cmd = ["flowreel", "compose", what, file, *extra, "-j", str(args.jobs), "-o", args.out]
    if args.frames:
        cmd += ["--frames", args.frames]
    if args.force:
        cmd.append("--force")
    return cmd


class ComposeCommand(BaseCommand):
    """The ``compose`` command group."""

    name = "compose"
    description = "Compose layouts and draw panels"
    category = "Compose"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["compose"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="compose_cmd", metavar="<action>")

        lay = _parser(
            actions, "layout", help="compose a layout's frames",
            description="Compose the frames of a layout file into OUT/<layout>/frame_00000.png: "
                        "its stations' shots are rendered and its panels drawn first. Frames "
                        "whose key did not change are skipped; a draft (--scale, --size) goes "
                        "to OUT/<layout>@<W>x<H>/.")
        lay.add_argument("layout", help="the layout file").completer = paths((".yml", ".yaml"))
        lay.add_argument("--scale", type=float, metavar="S",
                         help="compose at the layout's size times S (a draft), e.g. 0.5")
        lay.add_argument("--size", type=int, nargs=2, metavar=("W", "H"),
                         help="compose at W x H pixels (a draft)")
        _common(lay, "composed frames")

        pan = _parser(
            actions, "panel", help="draw a panel's frames",
            description="Draw the frames of a panel file into OUT/<panel>/frame_00000.png, "
                        "frame i at the panel's time i. Frames whose key did not change are "
                        "skipped. With -j N the frames are cut into N runs of consecutive "
                        "frames, each drawn by its own process.")
        pan.add_argument("panel", help="the panel file").completer = paths((".yml", ".yaml"))
        _common(pan, "frames")
        return p

    def execute(self, args, ctx):
        if not args.compose_cmd:
            ctx.error("give an action: flowreel compose --help")
            return 2
        if args.jobs < 1:
            raise CommandError("-j must be at least 1")
        try:
            return getattr(self, "do_" + args.compose_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename}") from None
        except (ValueError, LookupError) as exc:
            raise CommandError(str(exc.args[0]) if isinstance(exc, LookupError) and exc.args
                               else str(exc)) from None

    def do_layout(self, args, ctx):
        from flowreel.cli.jobs import run_single, slurm_wanted
        from flowreel.compose import layout
        if args.scale is not None and args.size is not None:
            raise CommandError("give --scale or --size, not both")
        if slurm_wanted(args):
            extra = (["--scale", f"{args.scale:g}"] if args.scale is not None else []) + \
                (["--size", *map(str, args.size)] if args.size else [])
            return run_single(ctx, Path(args.layout).stem, _as_job(args, "layout", args.layout,
                                                                   extra), "compose", args)
        frames = parse_frames(args.frames) if args.frames else None
        start = time.perf_counter()
        report = layout(args.layout, args.out, frames=frames, force=args.force,
                        scale=args.scale, size=tuple(args.size) if args.size else None,
                        progress=lambda e: ctx.out(f"  {e[1].name} {e[2]}"),
                        render={"jobs": args.jobs}, panels={"jobs": args.jobs})
        ctx.out(f"{report.count('composed')} composed, {report.count('skipped')} skipped in "
                f"{time.perf_counter() - start:.1f} s -> {report.folder}")
        return 0

    def do_panel(self, args, ctx):
        from flowreel.cli.jobs import run_single, slurm_wanted
        from flowreel.compose import panel
        if slurm_wanted(args):
            return run_single(ctx, Path(args.panel).stem, _as_job(args, "panel", args.panel, []),
                              "compose", args)
        frames = parse_frames(args.frames) if args.frames else None
        start = time.perf_counter()
        report = panel(args.panel, args.out, frames=frames, jobs=args.jobs, force=args.force,
                       progress=lambda e: ctx.out(f"  {e[1].name} {e[2]}"))
        ctx.out(f"{report.count('drawn')} drawn, {report.count('skipped')} skipped in "
                f"{time.perf_counter() - start:.1f} s -> {report.folder}")
        return 0
