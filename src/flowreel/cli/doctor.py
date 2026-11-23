"""``flowreel doctor``: the report of :mod:`flowreel.doctor`."""
from __future__ import annotations

import argparse

from shellkit import BaseCommand

EXAMPLES = """examples:
  flowreel doctor                  everything, drawing a test picture with each back end
  flowreel doctor --no-draw        quicker: no drawing
  flowreel doctor > doctor.txt     to send with a question

Marks: ! stops a film (exit status 1), ? worth knowing (an untested version).
Reference: docs/guide/commands.md."""


class DoctorCommand(BaseCommand):
    """The ``doctor`` command."""

    name = "doctor"
    description = "Check what FlowReel runs on: packages, ffmpeg, drawing, fonts, project"
    category = "Checks"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(
            self.name, help=self.description, epilog=EXAMPLES,
            description="Report the versions of Python, FlowReel and the packages it uses "
                        "(VTK and pyvista against the versions the tests run on), the "
                        "ffmpeg it finds, which off-screen back ends draw, the font, and "
                        "the project this folder is in. Exit status 1 when something "
                        "stops a film.",
            formatter_class=argparse.RawDescriptionHelpFormatter)
        p.add_argument("--no-draw", action="store_true",
                       help="leave out the off-screen drawing (a few seconds a back end)")
        p.add_argument("--timeout", type=float, default=None, metavar="S",
                       help="seconds each back end may take to draw (default 60)")
        return p

    def execute(self, args, ctx):
        from flowreel.doctor import doctor
        report = doctor(draw=not args.no_draw, timeout=args.timeout)
        ctx.out(report.text())
        return report.exit_code
