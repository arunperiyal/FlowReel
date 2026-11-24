"""Series computed from a tag's flow and written into the tag (plan Section 19.10, Phase 9
branch 4; ``flowreel data extract``).

Each kind of extract reads the tag's source, writes CSV under ``data/<tag>/series/``
and declares it under the body in ``domain.yml`` (:func:`~flowreel.project.domain.
declare_series`), so a panel or shot of the tag finds it by name. The constants come from
the tag's units: nothing is typed twice.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from flowreel.project.domain import DOMAIN_FILE, declare_series, load_domain, open_tag
from flowreel.project.imports import DataError, tag_folder


@dataclass
class Extracted:
    """What an extract wrote: the ``body``, the series ``name``, its ``csv`` and
    ``stations`` files, how many ``steps`` were computed now (and ``kept`` from the file),
    whether the declaration was written (``declared``), and ``coefficients``."""

    body: str
    name: str
    csv: Path
    stations: Path
    steps: int
    kept: int
    declared: bool
    coefficients: bool


def _one_body(domain, body: str | None) -> str:
    if body is not None:
        if body not in domain.bodies:
            raise DataError(f"tag {domain.tag!r} has no body {body!r} (bodies: "
                            f"{', '.join(domain.bodies) or 'none'})")
        return body
    if len(domain.bodies) != 1:
        raise DataError(f"tag {domain.tag!r} has {len(domain.bodies) or 'no'} bodies"
                        + (f" ({', '.join(domain.bodies)}): give --body" if domain.bodies
                           else ": declare one in its domain.yml"))
    return next(iter(domain.bodies))


def extract_sections(root, tag: str, *, body: str | None = None, axis: str | None = None,
                     sections: int = 48, steps: tuple | None = None, every: int = 1,
                     margin: float = 0.5, jobs: int = 1, force: bool = False,
                     say=print) -> Extracted:
    """The force on ``sections`` equal sections of ``body`` along its axis, at the saved
    steps from ``steps`` = (first, last) (default all), every ``every``th, from the
    tag's flow (:mod:`flowreel.project.sections`), with ``mu`` and ``p_inf`` from the
    tag's units, and the coefficients when ``rho``, ``u_inf`` and the body's diameter are
    known. Written as ``series/<body>_sections.csv`` and its stations file, and declared
    as the body's ``sections``. Steps already in the file are kept; ``force`` starts the
    file again and replaces a different declaration."""
    from flowreel.fields.basic import dynamic_pressure
    from flowreel.project.measure import long_axis
    from flowreel.project.sections import write
    if sections < 1 or every < 1 or jobs < 1:
        raise DataError("--sections, --every and --jobs must be at least 1")
    folder = tag_folder(root, tag)
    if not (folder / DOMAIN_FILE).is_file():
        raise DataError(f"no tag {tag!r}")
    domain = load_domain(folder)
    name = _one_body(domain, body)
    declared = domain.bodies[name]
    if "mu" not in domain.units:
        raise DataError(f"the wall shear needs the viscosity: give units.mu in "
                        f"data/{tag}/domain.yml")
    source = open_tag(domain)
    chosen = list(source.steps())
    if steps:
        first, last = steps
        chosen = [s for s in chosen if first <= s <= last]
        if not chosen:
            raise DataError(f"no saved step from {first} to {last}")
    chosen = chosen[::every]
    axis = axis or declared.axis or long_axis(source.body(chosen[0], name))
    if axis is None:
        raise DataError(f"no axis for {name!r}: declare it in data/{tag}/domain.yml or give "
                        f"--axis")
    u = domain.units
    q_d = (dynamic_pressure(u["rho"], u["u_inf"]) * declared.diameter
           if declared.diameter and {"rho", "u_inf"} <= set(u) else None)
    rel = f"series/{name}_sections.csv"
    out = folder / rel
    if force:
        for path in (out, out.with_name(out.stem + "_stations.csv")):
            path.unlink(missing_ok=True)
    params = {k: v for k, v in domain.params.items() if k in ("mu", "p_inf")}
    try:
        csv, stations, n = write(source, name, out, axis=axis, sections=sections,
                                 steps=chosen, params=params, margin=margin, q_d=q_d,
                                 jobs=jobs, say=say)
    except (LookupError, ValueError) as exc:
        raise DataError(str(exc.args[0]) if isinstance(exc, LookupError) and exc.args
                        else str(exc)) from None
    spec = {"file": rel, "by": "section", "stations": f"series/{stations.name}"}
    raw = yaml.safe_load((folder / DOMAIN_FILE).read_text()) or {}
    there = (((raw.get("bodies") or {}).get(name) or {}).get("series") or {}).get("sections")
    wrote = there != spec
    if wrote:
        try:
            declare_series(folder, name, "sections", spec, force=force)
        except ValueError as exc:
            raise DataError(str(exc)) from None
    return Extracted(name, "sections", csv, stations, n, len(chosen) - n, wrote, q_d is not None)
