"""``flowreel doctor``: one report of what FlowReel runs on, to read before a render or
paste into a question (plan Section 19.9, Phase 8 branch 2).

It says, each on a line or two:

- **Python and FlowReel:** their versions, and where FlowReel is installed from.
- **Packages:** each package FlowReel depends on, its version, and whether that is at
  least the minimum FlowReel declares. VTK and pyvista, which change what is drawn, are
  also checked against :data:`TESTED`, the oldest and newest versions the test suite
  runs on in CI (``.github/workflows/tests.yml``): a newer one is allowed, but untested.
- **ffmpeg:** the one FlowReel finds (:mod:`flowreel.film.ffmpeg`), or why it is
  unsuitable.
- **Off-screen drawing:** each back end tried, as ``flowreel jobs check`` does.
- **Fonts:** the bundled Lato, as matplotlib finds it.
- **Project:** inside one, its folder, shots and film (``flowreel project info``).

A problem that stops a film (a package older than FlowReel needs, no usable ffmpeg, no
back end that draws) makes the report fail; an untested version is only a note.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

#: The oldest and newest versions (major.minor) the test suite runs on in CI, of the
#: packages that decide what a frame or a caption looks like. The oldest are FlowReel's
#: declared minimums (tests/test_doctor.py checks); the newest is raised when CI's newest
#: job passes on a new release (matplotlib is held below 3.11: PLAN Section 24, q. 9).
TESTED = {"vtk": ("9.5", "9.7"), "pyvista": ("0.47", "0.49"), "matplotlib": ("3.8", "3.10")}

@dataclass
class Line:
    """One line of the report: ``what`` it is about, the ``text``, and its ``level``:
    ``ok``, ``note`` (worth knowing, not a problem) or ``problem`` (stops a film)."""

    what: str
    text: str
    level: str = "ok"


@dataclass
class Report:
    """The report's sections, each a title and its lines."""

    sections: list[tuple[str, list[Line]]] = field(default_factory=list)

    @property
    def problems(self) -> list[Line]:
        """The lines that stop a film."""
        return [line for _, lines in self.sections for line in lines
                if line.level == "problem"]

    @property
    def exit_code(self) -> int:
        """0 when nothing stops a film, else 1."""
        return 1 if self.problems else 0

    def text(self) -> str:
        """The report for the terminal: sections, their lines, and a verdict."""
        width = max((len(line.what) for _, lines in self.sections for line in lines),
                    default=0)
        out = []
        for title, lines in self.sections:
            out.append(f"{title}:")
            for line in lines:
                mark = {"ok": " ", "note": "?", "problem": "!"}[line.level]
                out.append(f" {mark} {line.what.ljust(width)}  {line.text}".rstrip())
        problems = self.problems
        out.append("everything FlowReel needs is here" if not problems else
                   f"{len(problems)} problem{'s' * (len(problems) != 1)} (marked !)")
        return "\n".join(out)


def version_tuple(text: str) -> tuple[int, ...]:
    """The leading numbers of a version: ``9.7.2`` -> ``(9, 7, 2)``, ``2.1.1rc1`` ->
    ``(2, 1, 1)``."""
    numbers = []
    for part in text.split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        numbers.append(int(m.group()))
        if m.group() != part:
            break
    return tuple(numbers)


def minimums() -> dict[str, str]:
    """The minimum version FlowReel declares for each dependency that has one
    (``pyproject.toml``, as installed)."""
    out = {}
    for req in metadata.requires("flowreel") or []:
        if "extra ==" in req:
            continue
        m = re.match(r"\s*([A-Za-z0-9_.\-]+)\s*>=\s*([\d.]+)", req)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def package_lines(installed=None) -> list[Line]:
    """A line for each dependency with a minimum: its version against the minimum and,
    for VTK and pyvista, against :data:`TESTED`. ``installed`` maps a name to its
    version, or ``None`` when it is not installed (default: as installed here)."""
    lines = []
    for name, least in minimums().items():
        have = installed(name) if installed else _installed(name)
        if have is None:
            lines.append(Line(name, f"missing (FlowReel needs {least} or newer)", "problem"))
            continue
        v = version_tuple(have)
        if v < version_tuple(least):
            lines.append(Line(name, f"{have}, older than FlowReel needs ({least})", "problem"))
        elif name.lower() in TESTED:
            low, high = TESTED[name.lower()]
            if v[:2] > version_tuple(high):
                lines.append(Line(name, f"{have}, newer than tested ({low} to {high}): "
                                  "untested, may draw differently", "note"))
            else:
                lines.append(Line(name, f"{have}, tested ({low} to {high})"))
        else:
            lines.append(Line(name, f"{have} (needs {least} or newer)"))
    return lines


def _installed(name: str) -> str | None:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def ffmpeg_lines() -> list[Line]:
    """The ffmpeg FlowReel uses, or why there is none it can use."""
    from flowreel.film import ffmpeg
    try:
        found = ffmpeg.find()
    except ffmpeg.FfmpegError as exc:
        return [Line("ffmpeg", str(exc), "problem")]
    version = ".".join(map(str, found.version))
    return [Line("ffmpeg", f"{version} at {found.ffmpeg}, with the encoder and filters "
                 "FlowReel uses")]


def backend_lines(timeout: float | None = None) -> list[Line]:
    """Each off-screen back end tried, as ``flowreel jobs check`` does, and the one
    FlowReel would use."""
    from flowreel.jobs import check
    report = check.check("auto", timeout or check.TIMEOUT)
    lines = [Line(r.backend, r.text()[len(r.backend):].strip()) for r in report.results]
    chosen = report.chosen or "none installed"
    lines.append(Line("used", f"{chosen}: {'works' if report.ok else 'does not work'}",
                      "ok" if report.ok else "problem"))
    return lines


def font_lines() -> list[Line]:
    """Lato, as matplotlib finds it (captions, cards and panels use it): the copy
    bundled with FlowReel, or one of the system's."""
    from matplotlib import font_manager

    from flowreel.compose.style import register_fonts
    from flowreel.scene.text import FONTS
    register_fonts()
    try:
        path = font_manager.findfont(font_manager.FontProperties(family="Lato"),
                                     fallback_to_default=False)
    except ValueError:
        return [Line("Lato", "not found: text falls back to DejaVu Sans", "note")]
    where = Path(path).resolve().parent
    which = "the copy bundled with FlowReel" if where == FONTS.resolve() else "the system's"
    return [Line("Lato", f"{which}, at {where}")]


def project_lines(start: str | Path | None = None) -> list[Line]:
    """The project holding ``start`` (default the current folder): its folder, shots
    and film; or that there is none."""
    from flowreel.project.info import info
    from flowreel.project.paths import find_root
    root = find_root(start)
    if root is None:
        return [Line("folder", "not in a project (flowreel project init makes one)")]
    found = info(root)
    lines = [Line("folder", str(root)),
             Line("shots", str(len(found.shots)) if found.shots else "none yet"),
             Line("film", found.film or "none")]
    if found.layouts:
        lines.append(Line("layouts", ", ".join(found.layouts)))
    if found.tags:
        lines.insert(1, Line("tags", ", ".join(n for n, _, _ in found.tags)))
        lines += [Line(f"tag {n}", f"{s} (flowreel data check {n})", "note")
                  for n, s, ok in found.tags if not ok]
    lines += [Line("error", e, "note") for e in found.errors]
    return lines


def doctor(start: str | Path | None = None, *, draw: bool = True,
           timeout: float | None = None) -> Report:
    """The report (see the module). ``draw=False`` leaves out the off-screen drawing,
    which takes a few seconds a back end; ``timeout`` is the seconds each may take."""
    import flowreel
    here = Path(flowreel.__file__).parent
    report = Report()
    report.sections.append(("FlowReel", [
        Line("flowreel", f"{flowreel.__version__} at {here}"),
        Line("python", f"{sys.version.split()[0]} at {sys.executable}")]))
    report.sections.append(("packages", package_lines()))
    report.sections.append(("ffmpeg", ffmpeg_lines()))
    if draw:
        report.sections.append(("off-screen drawing", backend_lines(timeout)))
    report.sections.append(("fonts", font_lines()))
    report.sections.append(("project", project_lines(start)))
    return report
