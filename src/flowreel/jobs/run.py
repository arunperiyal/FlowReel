"""Renders, composes and film builds as Slurm jobs (plan Section 19.6): the work behind
``--slurm FILE`` and ``--submit``.

:func:`render` plans a shot's render as a job array (:mod:`flowreel.jobs.split`) from
the measured cost of its frames, writes the script (:mod:`flowreel.jobs.script`) and,
with ``submit``, hands it to ``sbatch``. A shot not measured yet gets a measuring job
instead, which then runs the same command again on the node: by then it can be sized.
:func:`single` does the same for one command (``compose layout``, ``film build``).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from flowreel.jobs import partitions, script as script_mod, submit as submit_mod
from flowreel.jobs.spec import JobSpec

GB = 1024 ** 3
#: A single job (compose, film build) unless asked: cores, memory, time.
SINGLE = (4, 16 * GB, 2 * 3600)


@dataclass
class Submitted:
    """What was written and submitted: the ``script``, the Slurm ``job`` id (``None``
    when only written), the :class:`~flowreel.jobs.spec.JobSpec`, whether it is the
    ``measuring`` job of a shot not measured yet, the ``log`` pattern, the render's
    ``plan`` (``None`` otherwise) and ``notes`` to print."""

    script: Path
    job: str | None
    spec: JobSpec
    measuring: bool = False
    plan: object = None
    notes: list[str] = field(default_factory=list)

    @property
    def log(self) -> str:
        """The log file, with the job id in it once submitted."""
        log = self.spec.log_pattern.replace("%x", self.spec.name)
        if self.job:
            log = log.replace("%A", self.job).replace("%j", self.job).replace("%a", "*")
        return log

    def text(self) -> str:
        """What happened, for the terminal."""
        lines = list(self.notes)
        what = "measuring job" if self.measuring else (
            f"job array of {self.spec.tasks} task{'s' * (self.spec.tasks != 1)}"
            if self.spec.tasks else "job")
        lines.append(f"wrote {self.script} ({what})")
        if self.job:
            lines.append(f"submitted job {self.job}; log {self.log}")
        else:
            lines.append(f"submit with: sbatch {self.script}")
        return "\n".join(lines)


def _rel(path, workdir: Path) -> str:
    """``path`` relative to ``workdir`` when inside it, else absolute."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(workdir))
    except ValueError:
        return str(p)


def _write_and_submit(spec, commands, tasks, script_path: Path, workdir: Path, submit: bool,
                      written_by: str, kind: str, folder=None, frames=None) -> Submitted:
    text = script_mod.job_script(spec, commands, tasks, workdir=workdir, written_by=written_by)
    path = script_mod.write(script_path, text, spec, workdir)
    job = None
    if submit:
        job = submit_mod.submit(path, workdir)
        submit_mod.note(workdir, job, spec.name, kind, _rel(path, workdir),
                        None if folder is None else _rel(folder, workdir), frames)
    return Submitted(path, job, spec)


def render(shot, *, script: str | Path | None = None, submit: bool = False,
           out: str | Path = "frames", frames=None, scale: float | None = None,
           size: tuple[int, int] | None = None, backend: str = "auto", force: bool = False,
           missing: bool = False, cluster: str | None = None, partition: str | None = None,
           time: int | None = None, memory: int | None = None, cpus: int | None = None,
           threads: int = 1, max_running: int | None = None, after=(),
           workdir: str | Path | None = None) -> Submitted:
    """Write (and with ``submit``, submit) the job array that renders ``frames``
    (default all) of the shot file ``shot``. ``script`` defaults to
    ``jobs/<shot>.sh``; ``missing`` plans only the frames not drawn yet; the other
    options are those of ``shot render`` and :func:`~flowreel.jobs.split.plan_render`.
    The job runs in ``workdir`` (default the current folder)."""
    from flowreel.jobs import measured, split
    from flowreel.scene.rendering import _as_shot, draft_size, frame_folder
    from flowreel.scene.rendering import missing as missing_frames
    if missing and force:
        raise ValueError("give --missing or --force, not both")
    workdir = Path(workdir or os.getcwd()).resolve()
    shot_obj = _as_shot(shot)
    shot_arg = _rel(shot, workdir)
    out_arg = _rel(out, workdir)
    folder = frame_folder(out, shot_obj, draft_size(shot_obj.size, scale, size))
    script = Path(script) if script else workdir / "jobs" / f"{shot_obj.name}.sh"
    found = partitions.find(cluster)
    record = measured.load(folder)
    if record is None:
        then = render_command(shot_arg, script=_rel(script, workdir), out=out_arg, frames=frames,
                              scale=scale, size=size, backend=backend, force=force,
                              missing=missing, cluster=found.name, partition=partition,
                              time=time, memory=memory, cpus=cpus, threads=threads,
                              max_running=max_running)
        spec, commands = split.measure_job(found, shot_obj.name, shot_arg, then, out=out_arg,
                                           frame=min(frames) if frames else 0, scale=scale,
                                           size=size, backend=backend, after=after)
        path = script.with_name(script.stem + "_measure" + script.suffix)
        done = _write_and_submit(spec, commands, None, path, workdir, submit,
                                 f"flowreel shot render {shot_arg} --slurm", "measure")
        done.measuring = True
        done.notes.append(f"{shot_obj.name}: no measurement of a frame yet; the job measures "
                          f"one on the node, then plans and submits the render as {script.name}")
        return done
    todo = list(frames) if frames is not None else None
    if missing:
        todo = missing_frames(shot_obj, todo, out=out, scale=scale, size=size)
        if not todo:
            raise ValueError(f"{shot_obj.name}: every frame is drawn already")
    if todo is None:
        from flowreel.scene.rendering import Scene
        todo = list(range(Scene.make(shot_obj, size=draft_size(shot_obj.size, scale, size)).plan.n_frames))
    plan = split.plan_render(todo, record, found, partition=partition, cpus=cpus,
                             memory=memory, time=time, threads=threads,
                             max_running=max_running)
    spec = split.render_job(plan, shot_obj.name, after=after)
    tasks = split.render_commands(plan, shot_arg, out=out_arg, scale=scale, size=size,
                                  backend=backend)
    if force:
        for task in tasks:
            task[0].append("--force")
    done = _write_and_submit(spec, (), tasks, script, workdir, submit,
                             f"flowreel shot render {shot_arg} --slurm", "render",
                             folder, todo)
    done.plan = plan
    done.notes.append(plan.text())
    return done


def render_command(shot: str, *, script: str, out: str, frames=None, scale=None, size=None,
                   backend="auto", force=False, missing=False, cluster=None, partition=None,
                   time=None, memory=None, cpus=None, threads=1, max_running=None) -> list[str]:
    """The ``flowreel shot render ... --slurm SCRIPT --submit`` line that plans and
    submits a render, for the measuring job to run once it has measured."""
    from flowreel.jobs.split import frames_spec
    cmd = ["flowreel", "shot", "render", shot, "-o", out, "--slurm", script, "--submit"]
    if frames is not None:
        cmd += ["--frames", frames_spec(sorted(set(frames)))]
    if scale is not None:
        cmd += ["--scale", f"{scale:g}"]
    if size is not None:
        cmd += ["--size", str(size[0]), str(size[1])]
    if backend != "auto":
        cmd += ["--backend", backend]
    if force:
        cmd.append("--force")
    if missing:
        cmd.append("--missing")
    if cluster:
        cmd += ["--cluster", cluster]
    if partition:
        cmd += ["--partition", partition]
    if time is not None:
        cmd += ["--time", partitions.format_time(time)]
    if memory is not None:
        cmd += ["--mem", partitions.format_memory(memory)]
    if cpus is not None:
        cmd += ["--cpus", str(cpus)]
    if threads != 1:
        cmd += ["--threads", str(threads)]
    if max_running is not None:
        cmd += ["--max-running", str(max_running)]
    return cmd


def single(name: str, command: list[str], *, kind: str, script: str | Path | None = None,
           submit: bool = False, cluster: str | None = None, partition: str | None = None,
           time: int | None = None, memory: int | None = None, cpus: int | None = None,
           after=(), workdir: str | Path | None = None) -> Submitted:
    """Write (and with ``submit``, submit) one job that runs ``command`` (``compose
    layout``, ``film build``): :data:`SINGLE` cores, memory and time unless given, in the
    shortest partition that takes it unless named. ``script`` defaults to
    ``jobs/<name>.sh``."""
    workdir = Path(workdir or os.getcwd()).resolve()
    found = partitions.find(cluster)
    cpus = cpus or SINGLE[0]
    memory = memory or SINGLE[1]
    time = time or SINGLE[2]
    part = found.partition(partition) if partition else found.fitting(time, cpus, memory)
    spec = JobSpec(name, part, cpus=cpus, memory=memory, time=time,
                   after=tuple(str(a) for a in after)).check()
    script = Path(script) if script else workdir / "jobs" / f"{name}.sh"
    return _write_and_submit(spec, [command], None, script, workdir, submit,
                             " ".join(command[:3]) + " --slurm", kind)
