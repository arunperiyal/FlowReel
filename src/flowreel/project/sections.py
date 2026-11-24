"""A body's sectional force along its axis, step by step, as a series in long form (plan
Section 19.10, Phase 9 branch 4; ``flowreel data extract sections``).

For each saved step the wall is cut into ``sections`` equal strips along the body's axis
and the traction on each (pressure and wall shear, from the flow next to the wall:
:func:`flowreel.fields.wall.sectional_force`) is summed, then divided by the strip's
length: a force per unit length. The strips are fixed at the first step's extent along
the axis, so a section is the same piece of the body at every step.

Written as two files, declared as a series under the body (``by: section``,
:mod:`flowreel.project.series`; :func:`flowreel.project.extract.extract_sections` writes
the declaration into the tag's ``domain.yml``):

- ``<name>.csv``: ``time, section, fx, fy, fz``, and ``cx, cy, cz`` when the dynamic
  pressure and the body's diameter are known (``force per length / (q D)``, ``q = rho
  u_inf^2 / 2``);
- ``<name>_stations.csv``: ``section, station``, where along the axis each strip's
  centre is.

A step whose time is already in the file is kept, so a run cut short goes on where it
stopped, and a longer window adds only its new steps.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from flowreel.box import Box

AXES = "xyz"


@dataclass(frozen=True)
class Plan:
    """What :func:`one_step` needs, the same for every step: the ``body``'s name, the
    ``axis`` index, the number of ``sections``, the ``span`` (lo, hi) they divide, the
    ``margin`` of flow read round the wall, the fields' ``params`` (``mu``, ``p_inf``) and
    ``q_d`` (dynamic pressure times diameter, ``None``: no coefficients)."""

    body: str
    axis: int
    sections: int
    span: tuple[float, float]
    margin: float
    params: dict
    q_d: float | None


def one_step(source, step: int, plan: Plan) -> pd.DataFrame:
    """The rows of ``step``: ``time, section, fx, fy, fz`` (per unit length, the force
    on the body) and, with ``plan.q_d``, ``cx, cy, cz``."""
    from flowreel import fields
    from flowreel.compose.flow_cut import source_fields
    wall = source.body(step, plan.body).triangulate().clean()
    lo = np.asarray(wall.bounds[0::2]) - plan.margin
    hi = np.asarray(wall.bounds[1::2]) + plan.margin
    flow = source.flow(step, source_fields(source, ["sectional_force"]), Box(lo, hi))
    if not flow.n_cells:
        raise ValueError(f"step {step}: no flow cells round the body; make the margin "
                         f"larger than a cell")
    result = fields.compute(flow, ["sectional_force"], wall=wall, axis=plan.axis,
                            sections=plan.sections, span=plan.span,
                            **plan.params)["sectional_force"]
    per_length = np.asarray(result.force, float) / result.width
    rows = {"time": np.full(plan.sections, source.time(step)),
            "section": np.arange(plan.sections)}
    for k, name in enumerate("xyz"):
        rows[f"f{name}"] = per_length[:, k]
    if plan.q_d:
        for k, name in enumerate("xyz"):
            rows[f"c{name}"] = per_length[:, k] / plan.q_d
    return pd.DataFrame(rows)


def _work(args):
    source, step, plan = args
    return one_step(source, step, plan)


def stations(span: tuple[float, float], sections: int) -> np.ndarray:
    """The centre of each of ``sections`` equal strips of ``span``."""
    lo, hi = span
    width = (hi - lo) / sections
    return lo + width * (np.arange(sections) + 0.5)


def write(source, body: str, out: str | Path, *, axis: str, sections: int = 48,
          steps=None, params: dict | None = None, margin: float = 0.5,
          q_d: float | None = None, jobs: int = 1, say=print) -> tuple[Path, Path, int]:
    """Compute and write the series (see the module) of ``body`` at ``steps`` (default
    every saved one) into ``out`` and its stations file; returns ``(csv, stations,
    steps computed)``. Steps whose time ``out`` already holds are kept as they are."""
    out = Path(out)
    axis_index = AXES.index(axis) if isinstance(axis, str) else int(axis)
    steps = list(source.steps()) if steps is None else list(steps)
    if not steps:
        raise ValueError("no steps to compute")
    first = source.body(steps[0], body)
    span = (float(first.bounds[2 * axis_index]), float(first.bounds[2 * axis_index + 1]))
    plan = Plan(body, axis_index, int(sections), span, float(margin), dict(params or {}),
                q_d)
    old = pd.read_csv(out) if out.is_file() else None
    if old is not None and old["section"].nunique() != sections:
        raise ValueError(f"{out} has {old['section'].nunique()} sections, not {sections}: "
                         f"write the new count to another file")
    done = set() if old is None else {round(float(t), 9) for t in old["time"]}
    todo = [s for s in steps if round(float(source.time(s)), 9) not in done]
    say(f"{body}: {len(todo)} of {len(steps)} steps to compute ({len(steps) - len(todo)} "
        f"in {out.name} already), {sections} sections over {AXES[axis_index]} = "
        f"{span[0]:g} to {span[1]:g}")
    frames = [] if old is None else [old]
    if todo:
        work = [(source, s, plan) for s in todo]
        if jobs > 1 and len(todo) > 1:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                new = list(pool.map(_work, work))
        else:
            new = [_work(w) for w in work]
        frames += new
    table = pd.concat(frames, ignore_index=True).sort_values(["time", "section"])
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    table.to_csv(tmp, index=False, float_format="%.8g")
    tmp.replace(out)
    station_file = out.with_name(out.stem + "_stations.csv")
    pd.DataFrame({"section": np.arange(sections),
                  "station": stations(span, sections)}).to_csv(station_file, index=False,
                                                                float_format="%.8g")
    return out, station_file, len(todo)
