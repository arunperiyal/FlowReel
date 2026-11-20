"""``flowreel film``: build a film, check it, print its lengths, subtitles and chapters.

Each action is a thin layer over a library function (``flowreel.film.build.build``,
``flowreel.film.check.contact`` ...); the work and its checks live there. ``FILM`` is
the film file; left out, it is ``film.yml`` in the current folder.
"""
from __future__ import annotations

import argparse
import textwrap
import time

from shellkit import BaseCommand, CommandError, paths

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "film": """examples:
  flowreel film build
  flowreel film build --preview 480
  flowreel film build --only compare

Reference: docs/commands.md.""",
    "build": """examples:
  flowreel film build                        the film, from ./film.yml
  flowreel film build talk.yml --mute        without its sound
  flowreel film build --preview 480          and film_480p.mp4, to send to someone
  flowreel film build --preview 720 --crf 23 a better preview copy
  flowreel film build --only compare         one shot alone, as film_compare.mp4
  flowreel film build --force                build every clip again""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _film_arg(parser):
    parser.add_argument("film", nargs="?", default="film.yml", metavar="FILM",
                        help="the film file (default ./film.yml)"
                        ).completer = paths((".yml", ".yaml"))


def _clips_arg(parser):
    parser.add_argument("--clips", metavar="DIR",
                        help="folder of the clips (default clips/ beside the film file)")
    parser.add_argument("-j", "--jobs", type=int, default=1, metavar="N",
                        help="processes drawing a layout's live panels (default 1)")


class FilmCommand(BaseCommand):
    """The ``film`` command group."""

    name = "film"
    description = "Build a film and check it"
    category = "Film"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["film"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="film_cmd", metavar="<action>")

        b = _parser(
            actions, "build", help="build the film from its file",
            description="Build every shot's finished clip (clips whose key did not change "
                        "are kept), join them into the film's output with its sound and "
                        "chapters, and write film.srt and chapters.txt beside it. Prints "
                        "each shot's planned and measured length.")
        _film_arg(b)
        b.add_argument("--only", metavar="SHOT",
                       help="build this shot's finished clip alone, as film_SHOT.mp4, silent")
        b.add_argument("--mute", action="store_true", help="build the film without its sound")
        b.add_argument("--force", action="store_true",
                       help="build every clip again, even when its key did not change")
        b.add_argument("--preview", type=int, metavar="HEIGHT",
                       help="also write film_<HEIGHT>p.mp4, scaled to HEIGHT pixels (even)")
        b.add_argument("--crf", type=int, metavar="N",
                       help="quality of the preview copy, 0 to 51, lower is better (default 28)")
        _clips_arg(b)
        return p

    def execute(self, args, ctx):
        from flowreel.film.ffmpeg import FfmpegError
        if not args.film_cmd:
            ctx.error("give an action: flowreel film --help")
            return 2
        if getattr(args, "jobs", 1) < 1:
            raise CommandError("-j must be at least 1")
        try:
            return getattr(self, "do_" + args.film_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename or exc}") from None
        except KeyError as exc:
            raise CommandError(str(exc.args[0]) if exc.args else str(exc)) from None
        except (ValueError, FfmpegError) as exc:
            raise CommandError(str(exc)) from None

    def do_build(self, args, ctx):
        from flowreel.film.build import PREVIEW_CRF, build
        if args.crf is not None and args.preview is None:
            raise CommandError("--crf sets the preview copy's quality; give --preview too")
        start = time.perf_counter()
        built = build(args.film, folder=args.clips, force=args.force, mute=args.mute,
                      preview=args.preview,
                      crf=PREVIEW_CRF if args.crf is None else args.crf, only=args.only,
                      panels={"jobs": args.jobs})
        for line in built.table():
            ctx.out(line)
        ctx.out(f"built in {time.perf_counter() - start:.1f} s")
        return 0
