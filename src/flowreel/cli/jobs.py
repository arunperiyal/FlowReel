"""The Slurm options of commands (plan Section 19.6).

:func:`add_slurm_args`
gives ``shot render``, ``compose`` and ``film build`` their ``--slurm FILE`` and
``--submit`` options; the work is in :mod:`flowreel.jobs.run`.
"""
from __future__ import annotations

from shellkit import CommandError



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
