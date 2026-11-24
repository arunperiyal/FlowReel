"""``flowreel shot``: render a shot, preview it, measure it, write a template.

Each action is a thin layer over a library function (``flowreel.scene.render``,
``flowreel.scene.memory.measure``); the work and its checks live there.
"""
from __future__ import annotations

import argparse
import textwrap
import time
from pathlib import Path

from shellkit import BaseCommand, CommandError, add_context_arg, paths

from flowreel.scene.backend import BACKENDS
from flowreel.scene.errors import ConfigError


def parse_frames(text: str) -> list[int]:
    """Frame numbers from ``A``, ``A:B`` (A to B, both included), ``A:B:E`` (every
    E-th) or a comma list of these, such as ``0:10,24,40:120:20``."""
    out: list[int] = []
    for part in text.split(","):
        bits = part.strip().split(":")
        try:
            nums = [int(b) for b in bits]
        except ValueError:
            raise CommandError(f"--frames: {part!r} is not A, A:B or A:B:E (whole numbers)") from None
        if len(nums) == 1:
            out.append(nums[0])
        elif len(nums) in (2, 3):
            step = nums[2] if len(nums) == 3 else 1
            if step < 1 or nums[1] < nums[0]:
                raise CommandError(f"--frames: {part!r} needs A <= B and E >= 1")
            out.extend(range(nums[0], nums[1] + 1, step))
        else:
            raise CommandError(f"--frames: {part!r} is not A, A:B or A:B:E")
    if any(n < 0 for n in out):
        raise CommandError("--frames: frame numbers start at 0")
    return out


EXAMPLES = {
    "shot": """examples:
  flowreel shot template carve -o carve.yml --layers body,iso
  flowreel shot preview carve.yml
  flowreel shot memory carve.yml
  flowreel shot render carve.yml -j 16

In the shell, `use shot:carve.yml` and the shot can be left out.
Reference: docs/guide/commands.md.""",
    "render": """examples:
  flowreel shot render carve.yml -j 16            every frame, 16 at a time
  flowreel shot render carve.yml --frames 0:48:4  frames 0, 4, ... 48
  flowreel shot render carve.yml --scale 0.5      a half-size draft, in frames/carve@960x540/
  flowreel shot render carve.yml --force          draw again even if nothing changed
  flowreel shot render carve.yml --submit         as a Slurm job array, sized from a
                                                  measured frame (docs/guide/making/slurm.md)
  flowreel shot render carve.yml --slurm carve.sh --max-running 2   write the script only
  flowreel shot render carve.yml --submit --missing                 only frames not drawn""",
    "preview": """examples:
  flowreel shot preview carve.yml                 every 10th frame at a quarter size
  flowreel shot preview carve.yml --every 4 --scale 0.5""",
    "memory": """examples:
  flowreel shot memory carve.yml                  measure frame 0, suggest -j
  flowreel shot memory carve.yml --frame 200 --threads 2""",
    "template": """examples:
  flowreel shot template                          print a shot with a body layer
  flowreel shot template wake -o wake.yml --layers body,slice,iso""",
}


def _parser(actions, name, help, description):
    # Raw, so the examples keep their columns; the description is wrapped here instead.
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _shot_arg(parser):
    add_context_arg(parser, "shot", help="shot file (default: the shot set with use shot:FILE)")


def _draft_args(parser, scale_default=None):
    parser.add_argument("--scale", type=float, default=scale_default, metavar="S",
                        help="draw at the shot's size times S (a draft), e.g. 0.5")
    parser.add_argument("--size", type=int, nargs=2, metavar=("W", "H"),
                        help="draw at W x H pixels (a draft)")


def _run_args(parser):
    parser.add_argument("-j", "--jobs", type=int, default=1, metavar="N",
                        help="frames drawn at once, each in its own process (default 1)")
    parser.add_argument("--threads", type=int, metavar="T",
                        help="threads per job (default: min(4, cores / jobs))")
    parser.add_argument("--backend", choices=BACKENDS, default="auto",
                        help="off-screen OpenGL: auto (OSMesa, else EGL), osmesa, egl or x")
    parser.add_argument("--no-memory-check", dest="check_memory", action="store_false",
                        help="draw even if the jobs look too big for the free memory")
    parser.add_argument("-o", "--out", metavar="DIR",
                        help="folder of the frame folders (default frames/ at the project root)")


class ShotCommand(BaseCommand):
    """The ``shot`` command group."""

    name = "shot"
    description = "Render, preview and measure shots"
    category = "Shots"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["shot"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="shot_cmd", metavar="<action>")

        r = _parser(
            actions, "render", help="render a shot's frames",
            description="Render a shot's frames to OUT/<shot>/frame_00000.png. Frames whose "
                        "key did not change are skipped; a draft (--scale, --size) goes to "
                        "OUT/<shot>@<W>x<H>/.")
        _shot_arg(r)
        r.add_argument("--frames", metavar="SPEC",
                       help="frames to draw: A, A:B (both included), A:B:E, or a comma list")
        _draft_args(r)
        r.add_argument("--force", action="store_true",
                       help="draw the frames even when their key did not change")
        r.add_argument("--save-vtp", metavar="DIR",
                       help="instead of drawing frames, save the scene's surfaces at each "
                            "step the frames show into DIR, to open with 'camera edit --vtp "
                            "DIR' on a machine with a display")
        _run_args(r)
        from flowreel.cli.jobs import add_slurm_args
        add_slurm_args(r, render=True)

        pv = _parser(
            actions, "preview", help="small frames, every N-th, to check timing",
            description="Draw every N-th frame (and the last) at a small size, into "
                        "OUT/<shot>@<W>x<H>/: a quick look at the timing before a full render.")
        _shot_arg(pv)
        pv.add_argument("--every", type=int, default=10, metavar="N",
                        help="draw frames 0, N, 2N, ... and the last (default 10)")
        _draft_args(pv, scale_default=0.25)
        _run_args(pv)

        m = _parser(
            actions, "memory", help="memory of one frame and a safe -j for this machine",
            description="Draw one frame in a fresh process, as render does, and report its "
                        "peak memory, the free memory and the number of jobs that fit.")
        _shot_arg(m)
        m.add_argument("--frame", type=int, default=0, metavar="N",
                       help="frame to measure (default 0: in a frozen shot, the one that contours)")
        _draft_args(m)
        m.add_argument("--threads", type=int, metavar="T",
                       help="threads per job; caps the suggested jobs at cores / T")
        m.add_argument("--backend", choices=BACKENDS, default="auto",
                       help="off-screen OpenGL: auto, osmesa, egl or x")
        m.add_argument("-o", "--out", metavar="DIR",
                       help="folder of the frame folders, whose measurement sizes Slurm "
                            "jobs (default frames/ at the project root)")

        t = _parser(
            actions, "template", help="write a commented shot file with the defaults",
            description="Print (or write with -o) a shot file with every key and every "
                        "option of the chosen layers at its default, each with a comment.")
        t.add_argument("name", nargs="?", default="my_shot", help="the shot's name (default my_shot)")
        t.add_argument("--layers", default="body", metavar="TYPES",
                       help="comma list of layer types, e.g. body,slice,iso (default body)")
        t.add_argument("-o", "--output", metavar="FILE",
                       help="write to FILE instead of printing").completer = paths((".yml", ".yaml"))
        t.add_argument("--force", action="store_true", help="overwrite FILE if it exists")
        return p

    def execute(self, args, ctx):
        if not args.shot_cmd:
            ctx.error("give an action: flowreel shot --help")
            return 2
        if args.shot_cmd != "template":
            from flowreel.cli.project import project_root
            root = project_root(ctx, getattr(args, "shot", None))
            if getattr(args, "out", None) is None:
                args.out = str(root / "frames")
        try:
            return getattr(self, "do_" + args.shot_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename}") from None

    # -- render ----------------------------------------------------------------------

    def do_render(self, args, ctx):
        from flowreel.cli.jobs import slurm_wanted
        frames = parse_frames(args.frames) if args.frames else None
        if args.save_vtp:
            if slurm_wanted(args):
                raise CommandError("--save-vtp runs here, not as a Slurm job")
            return _save_vtp(args, ctx, frames)
        if slurm_wanted(args):
            return _render_on_slurm(args, ctx, frames)
        if args.missing:
            raise CommandError("--missing is for --slurm or --submit; a render here skips "
                               "drawn frames anyway")
        return _render(args, ctx, frames, args.scale, args.size, args.force)


    # -- preview and memory -------------------------------------------------------------

    def do_preview(self, args, ctx):
        from flowreel.scene.rendering import Scene
        if args.every < 1:
            raise CommandError("--every must be at least 1")
        n = Scene.make(args.shot).plan.n_frames
        frames = sorted(set(range(0, n, args.every)) | {n - 1})
        return _render(args, ctx, frames, None if args.size else args.scale, args.size, False)

    def do_memory(self, args, ctx):
        from flowreel.scene.memory import measure
        if args.scale is not None and args.size is not None:
            raise CommandError("give --scale or --size, not both")
        try:
            report = measure(args.shot, args.frame, scale=args.scale,
                             size=tuple(args.size) if args.size else None,
                             threads=args.threads, backend=args.backend, out=args.out)
        except (ValueError, IndexError) as exc:
            raise CommandError(str(exc)) from None
        ctx.out(report.text())
        return 0


    # -- template -----------------------------------------------------------------------

    def do_template(self, args, ctx):
        from flowreel.scene.template import template
        layers = [n.strip() for n in args.layers.split(",") if n.strip()]
        try:
            text = template(args.name, layers)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        if not args.output:
            ctx.out(text, end="")
            return 0
        path = Path(args.output)
        if path.exists() and not args.force:
            raise CommandError(f"{path} exists (use --force to overwrite)")
        path.write_text(text)
        ctx.out(f"wrote {path}")
        return 0


def _save_vtp(args, ctx, frames) -> int:
    from flowreel.editor.surfaces import save_shot_surfaces
    from flowreel.scene.rendering import Scene
    start = time.perf_counter()
    try:
        plan = Scene.make(args.shot).plan
        indices = range(plan.n_frames) if frames is None else frames
        steps = sorted({plan.time.step(i) for i in indices if 0 <= i < plan.n_frames})
        if not steps:
            raise CommandError(f"no frame of {args.frames} is in the shot (0 to {plan.n_frames - 1})")
        saved = save_shot_surfaces(args.shot, args.save_vtp, steps, backend=args.backend)
    except (ValueError, IndexError) as exc:
        raise CommandError(str(exc)) from None
    ctx.out(f"saved the surfaces of {len(saved)} step{'s' * (len(saved) != 1)} "
            f"({', '.join(map(str, saved))}) in {time.perf_counter() - start:.1f} s -> "
            f"{args.save_vtp}")
    return 0


def _render_on_slurm(args, ctx, frames) -> int:
    from flowreel.cli.jobs import slurm_options
    from flowreel.jobs import run
    from flowreel.jobs.submit import SlurmError
    if args.scale is not None and args.size is not None:
        raise CommandError("give --scale or --size, not both")
    if args.max_running is not None and args.max_running < 1:
        raise CommandError("--max-running must be at least 1")
    try:
        done = run.render(args.shot, out=args.out, frames=frames, scale=args.scale,
                          size=tuple(args.size) if args.size else None, backend=args.backend,
                          force=args.force, missing=args.missing, threads=args.threads or 1,
                          max_running=args.max_running, **slurm_options(args))
    except (SlurmError, LookupError, ValueError, KeyError) as exc:
        raise CommandError(str(exc.args[0]) if isinstance(exc, (LookupError, KeyError))
                           and exc.args else str(exc)) from None
    ctx.out(done.text())
    return 0


def _render(args, ctx, frames, scale, size, force) -> int:
    from flowreel.scene import render
    if scale is not None and size is not None:
        raise CommandError("give --scale or --size, not both")
    if args.jobs < 1:
        raise CommandError("-j must be at least 1")
    start = time.perf_counter()
    count = {"n": 0}

    def progress(result):
        count["n"] += 1
        took = f" {result.seconds:.1f} s" if result.status == "rendered" else ""
        ctx.out(f"  {result.path.name} {result.status}{took}")

    try:
        report = render(args.shot, frames, out=args.out, jobs=args.jobs, threads=args.threads,
                        backend=args.backend, force=force, scale=scale,
                        size=tuple(size) if size else None, progress=progress,
                        check_memory=args.check_memory)
    except (ValueError, IndexError) as exc:
        raise CommandError(str(exc)) from None
    ctx.out(f"{report.count('rendered')} rendered, {report.count('skipped')} skipped in "
            f"{time.perf_counter() - start:.1f} s -> {report.folder} "
            f"(backend {report.backend or 'vtk default'})")
    return 0
