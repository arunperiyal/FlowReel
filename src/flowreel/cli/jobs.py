"""``flowreel jobs`` and the Slurm options of other commands (plan Section 19.6).

``jobs partitions`` lists the clusters FlowReel knows, ``jobs check`` tries off-screen
drawing, ``jobs status`` says how FlowReel's jobs are doing. :func:`add_slurm_args`
gives ``shot render``, ``compose`` and ``film build`` their ``--slurm FILE`` and
``--submit`` options; the work is in :mod:`flowreel.jobs.run`.
"""
from __future__ import annotations

import argparse
import textwrap
import time as _time
from pathlib import Path

from shellkit import BaseCommand, CommandError

EXAMPLES = {
    "jobs": """examples:
  flowreel jobs partitions
  flowreel jobs check
  flowreel jobs status

Reference: docs/slurm.md and docs/commands.md.""",
    "partitions": """examples:
  flowreel jobs partitions                   every cluster, this one marked
  flowreel jobs partitions --cluster airavata""",
    "check": """examples:
  flowreel jobs check                        try each off-screen backend
  flowreel jobs check --backend egl          exit 1 unless EGL works""",
    "status": """examples:
  flowreel jobs status                       the jobs submitted from this folder
  flowreel jobs status 1310 1311             these jobs""",
}


def add_slurm_args(parser, render: bool = False) -> None:
    """``--slurm FILE``, ``--submit`` and the job's size, for a command that can run as a
    Slurm job (``render``: also the options of a job array)."""
    g = parser.add_argument_group("Slurm (run as a job on a cluster; docs/slurm.md)")
    g.add_argument("--slurm", metavar="FILE",
                   help="write a Slurm job script to FILE instead of running here")
    g.add_argument("--submit", action="store_true",
                   help="submit the job with sbatch (the script goes to jobs/NAME.sh unless "
                        "--slurm FILE)")
    g.add_argument("--cluster", metavar="NAME",
                   help="the cluster (default: FLOWREEL_CLUSTER, or this host's)")
    g.add_argument("--partition", metavar="NAME",
                   help="the partition (default: the shortest that takes the job)")
    g.add_argument("--time", metavar="T",
                   help="time a job may run: 90m, 3h, 1-12:00:00 (default: estimated)")
    g.add_argument("--mem", metavar="SIZE",
                   help="memory of a job: 32G, 500M (default: worked out)")
    g.add_argument("--cpus", type=int, metavar="N",
                   help="cores of a job (default: 16 for a render, 4 otherwise)")
    g.add_argument("--after", metavar="JOBID", action="append", default=[],
                   help="start only when job JOBID ended well (may be repeated)")
    if render:
        g.add_argument("--max-running", type=int, metavar="N",
                       help="at most N tasks of the render at once, so it takes part of a node")
        g.add_argument("--missing", action="store_true",
                       help="plan tasks only for frames not drawn yet")


def slurm_wanted(args) -> bool:
    """Whether the command should become a job instead of running here."""
    return bool(getattr(args, "slurm", None) or getattr(args, "submit", False))


def slurm_options(args) -> dict:
    """The job options of ``args``, parsed (times to seconds, memory to bytes)."""
    from flowreel.jobs.partitions import parse_memory, parse_time
    try:
        time = parse_time(args.time) if args.time else None
        memory = parse_memory(args.mem) if args.mem else None
    except ValueError as exc:
        raise CommandError(str(exc)) from None
    if args.cpus is not None and args.cpus < 1:
        raise CommandError("--cpus must be at least 1")
    for job in args.after:
        if not job.replace("_", "").isdigit():
            raise CommandError(f"--after: expected a job id such as 1310, got {job!r}")
    return {"script": args.slurm, "submit": args.submit, "cluster": args.cluster,
            "partition": args.partition, "time": time, "memory": memory, "cpus": args.cpus,
            "after": tuple(args.after)}


def job_path(path) -> str:
    """``path`` as a job's command line gives it: relative to the folder the job runs in
    (the project root, :func:`flowreel.jobs.run._workdir`) when inside it, else absolute."""
    from flowreel.jobs.run import _rel, _workdir
    return _rel(path, _workdir(None))


def run_single(ctx, name: str, command: list[str], kind: str, args) -> int:
    """Write or submit ``command`` as one job, from a command's ``args``."""
    from flowreel.jobs import run
    from flowreel.jobs.partitions import format_memory, format_time
    done = run.single(name, command, kind=kind, **slurm_options(args))
    s = done.spec
    ctx.out(f"{s.cpus} cores, {format_memory(s.memory)}, {format_time(s.time)} on "
            f"{s.partition.cluster} {s.partition.name}")
    ctx.out(done.text())
    return 0


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


class JobsCommand(BaseCommand):
    """The ``jobs`` command group."""

    name = "jobs"
    description = "Slurm: partitions, the off-screen check, job status"
    category = "Jobs"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["jobs"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="jobs_cmd", metavar="<action>")
        a = _parser(actions, "partitions", help="the clusters and partitions FlowReel knows",
                    description="List the clusters and partitions FlowReel knows (its own "
                                "table and ~/.flowreel/partitions.yml), marking the cluster "
                                "this machine is part of.")
        a.add_argument("--cluster", metavar="NAME", help="only this cluster")
        c = _parser(actions, "check", help="try drawing off-screen with each backend",
                    description="Draw a tiny picture with each off-screen backend (OSMesa, "
                                "EGL, X when there is a display), each in its own process, "
                                "and say which work. Exits 1 when the chosen one does not: "
                                "every job script runs it first.")
        c.add_argument("--backend", default="auto", choices=("auto", "osmesa", "egl", "x"),
                       help="the backend renders would use (default auto)")
        c.add_argument("--timeout", type=float, default=60.0, metavar="S",
                       help="seconds a backend may take (default 60)")
        s = _parser(actions, "status", help="how FlowReel's jobs are doing",
                    description="Slurm's state of the jobs submitted from this folder (or "
                                "the ones given), and for renders the frames drawn since "
                                "they were submitted.")
        s.add_argument("jobs", nargs="*", metavar="JOBID", help="job ids (default: this "
                       "folder's jobs, from .flowreel/jobs.json)")
        s.add_argument("--all", action="store_true",
                       help="every job of this folder, not only the last ten")
        return p

    def execute(self, args, ctx):
        from flowreel.jobs.submit import SlurmError
        from flowreel.scene.errors import ConfigError
        if not args.jobs_cmd:
            ctx.error("give an action: flowreel jobs --help")
            return 2
        try:
            return getattr(self, "do_" + args.jobs_cmd)(args, ctx)
        except (ConfigError, SlurmError, LookupError, ValueError) as exc:
            raise CommandError(str(exc.args[0]) if isinstance(exc, LookupError) and exc.args
                               else str(exc)) from None

    def do_partitions(self, args, ctx):
        from flowreel.jobs import partitions as p
        clusters = p.load()
        try:
            here = p.find(None, clusters).name
        except LookupError:
            here = None
        names = [args.cluster] if args.cluster else list(clusters)
        for name in names:
            if name not in clusters:
                raise CommandError(f"no cluster {name!r} (clusters: {', '.join(clusters)})")
            c = clusters[name]
            ctx.out(f"{name}{'  (this machine)' if name == here else ''}")
            for part in c.partitions.values():
                node = ", ".join(x for x in (
                    f"{part.cpus} cores" if part.cpus else "",
                    f"{part.job_cpus} a job" if part.max_cpus else "",
                    p.format_memory(part.memory) if part.memory else "") if x) or "size not known"
                kind = "shared" if part.shared else "whole nodes"
                ctx.out(f"  {part.name:10s} {p.format_time(part.time):>11s}  {node:28s} {kind:12s}"
                        f"{part.note}".rstrip())
        return 0

    def do_check(self, args, ctx):
        from flowreel.jobs.check import check
        report = check(args.backend, args.timeout)
        ctx.out(report.text())
        return report.exit_code

    def do_status(self, args, ctx):
        from flowreel.jobs.partitions import format_time
        from flowreel.jobs.submit import frames_done, notes, state_text, status
        from flowreel.project.paths import find_root
        base = find_root() or Path.cwd()
        noted = {n["job"]: n for n in notes(base)}
        if args.jobs:
            jobs = list(args.jobs)
        else:
            jobs = list(noted) if args.all else list(noted)[-10:]
        if not jobs:
            ctx.out("no jobs submitted from this folder (give job ids)")
            return 0
        states = status(jobs)
        by_job: dict[str, list] = {}
        for s in states:
            by_job.setdefault(s.job.split("_")[0], []).append(s)
        for job in jobs:
            n = noted.get(job, {})
            found = by_job.get(job, [])
            head = f"{job}  {n.get('name') or (found[0].name if found else '?')}"
            if n.get("kind"):
                head += f" ({n['kind']})"
            if n.get("submitted"):
                head += f", submitted {format_time(round(_time.time() - n['submitted']))} ago"
            ctx.out(head)
            if not found:
                ctx.out("  not known to Slurm (squeue, sacct)")
            counts: dict[str, int] = {}
            for s in found:
                counts[s.state] = counts.get(s.state, 0) + 1
            if len(found) == 1:
                ctx.out("  " + state_text(found[0]))
            elif found:
                ctx.out("  " + ", ".join(f"{k} {v}" for k, v in counts.items()))
            if n.get("folder") and n.get("frames"):
                drawn = frames_done(base / n["folder"], n["frames"], n["submitted"])
                ctx.out(f"  frames drawn since: {drawn} of {len(n['frames'])} ({n['folder']})")
        return 0
