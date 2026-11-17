"""``flowreel project init``: a ``flowreel.yml`` with one body per surface zone.

Each zone of the source becomes a body under its zone's name. A slender zone becomes a
beam body, with its axis and diameter measured from the surface at one step
(:mod:`flowreel.project.measure`). The supports and series are left to fill, written commented out: a PLT file does not say how
a body is held, and a guess there would be drawn as if it were known. The result loads
as it is.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

from flowreel.project import PROJECT_FILE
from flowreel.project.bodies import SUPPORTS
from flowreel.project.measure import AXES, diameter, long_axis

COLUMN = 38


def _num(v: float) -> str:
    return f"{v:.4g}"


def _line(text: str, comment: str = "") -> str:
    return f"{text.ljust(COLUMN)}# {comment}" if comment else text


def _key(name: str) -> str:
    text = yaml.safe_dump(name, default_flow_style=True).strip()
    return text.removesuffix("...").strip()


def body_block(zone: str, surface) -> str:
    """The YAML of one declared body for ``zone``, measured from ``surface``."""
    pts = np.asarray(surface.points)
    ext = np.ptp(pts, axis=0)
    axis = long_axis(surface)
    lines = [f"  {_key(zone)}:", f"    zone: {_key(zone)}"]
    if axis is None:
        lines.append(_line("    # axis: x", "not slender, so not a beam: "
                           + " x ".join(_num(e) for e in ext) + "; give one to make it a beam"))
    else:
        k = AXES[axis]
        across = max(np.delete(ext, k))
        lines.append(_line(f"    axis: {axis}", f"measured: {_num(ext[k])} long, {_num(across)} across"))
        try:
            d = diameter(surface, axis)
            lines.append(_line(f"    diameter: {_num(d)}", "measured from the surface; check it"))
        except ValueError as exc:
            lines.append(_line("    # diameter: 1.0", f"could not measure ({exc})"))
        lo, hi = float(pts[:, AXES[axis]].min()), float(pts[:, AXES[axis]].max())
        lines += [_line("    # ends:", "how it is held: " + ", ".join(SUPPORTS)),
                  f"    #   - {{at: {_num(lo)}, support: clamped}}",
                  f"    #   - {{at: {_num(hi)}, support: clamped}}"]
    lines += [_line("    # series:", "time histories as CSV (docs/bodies.md)"),
              f"    #   displacement: {{file: data/{zone}_displacement.csv}}"]
    return "\n".join(lines)


def bodies_yaml(source, step: int | None = None, label: str | None = None) -> str:
    """The text of a ``flowreel.yml`` declaring every surface zone of ``source``, measured
    at ``step`` (default the first). ``label`` names the source in the header. Raises
    ``LookupError`` when the source has no surface zone."""
    zones = source.bodies()
    if not zones:
        raise LookupError(f"{source.name}: the source has no surface zone to declare; "
                          "write bodies: by hand (docs/bodies.md)")
    step = source.steps()[0] if step is None else step
    head = [f"# flowreel.yml written by `flowreel project init` from {label or source.name}"
            f" at step {step}.",
            "# Reference: docs/bodies.md. Axes and diameters are measured; supports and",
            "# series are left to fill (uncomment and edit).",
            "bodies:"]
    blocks = [body_block(z, source.body(step, z)) for z in zones]
    return "\n".join(head) + "\n" + "\n".join(blocks) + "\n"


def init_project(folder: str | Path, source, step: int | None = None, *,
                 label: str | None = None, force: bool = False) -> Path:
    """Write ``folder/flowreel.yml`` from ``source`` (:func:`bodies_yaml`); returns its
    path. Raises ``FileExistsError`` unless ``force``."""
    path = Path(folder) / PROJECT_FILE
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists (use --force to overwrite)")
    text = bodies_yaml(source, step, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path
