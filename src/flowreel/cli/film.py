"""``flowreel film``: build a film, check it, print its lengths, subtitles and chapters.

Each action is a thin layer over a library function (``flowreel.film.build.build``,
``flowreel.film.check.contact`` ...); the work and its checks live there. ``FILM`` is
the film file; left out, it is ``film.yml`` of the ``project`` context (``use
project:DIR`` in the shell), else ``film.yml`` in the current folder.
"""
from __future__ import annotations

import argparse
import textwrap
import time

from pathlib import Path

from shellkit import BaseCommand, CommandError, add_context_arg, paths

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
    "check": """examples:
  flowreel film check                        a still at the middle of each caption
  flowreel film check --at freeze            one at each freeze
  flowreel film check --at every:10          one every 10 seconds
  flowreel film check --columns 6 --width 320 -o sheet.png""",
    "lengths": """examples:
  flowreel film lengths                      planned, and measured from the last build
  flowreel film lengths talk.yml""",
    "srt": """examples:
  flowreel film srt                          film.srt beside the film
  flowreel film srt -o captions.srt""",
    "chapters": """examples:
  flowreel film chapters                     print chapters.txt, for YouTube
  flowreel film chapters -o chapters.txt""",
    "template": """examples:
  flowreel film template                     print a film file with the defaults
  flowreel film template wake --fps 30 -o film.yml""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _project_film(store, namespace):
    """``film.yml`` of the project context, when one is set."""
    folder = store.get("project")
    return None if folder is None else str(Path(folder) / "film.yml")


def _film_arg(parser):
    add_context_arg(parser, "project", "film", required=False, default="film.yml",
                    resolve=_project_film, metavar="FILM",
                    help="the film file (default: film.yml of the project set with "
                         "use project:DIR, else ./film.yml)").completer = paths((".yml", ".yaml"))


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

        c = _parser(
            actions, "check", help="contact sheet of stills, with the text in place",
            description="Draw contact.png beside the film: stills of the finished film, each "
                        "labelled with its time and shot, the captions drawn as they show. "
                        "Missing finished clips are built; the film is not joined.")
        _film_arg(c)
        c.add_argument("--at", default="caption", metavar="WHEN",
                       help="caption (middle of each caption), freeze (middle of each "
                            "freeze) or every:S (every S seconds); default caption")
        c.add_argument("--columns", type=int, default=4, metavar="N",
                       help="stills across the sheet (default 4)")
        c.add_argument("--width", type=int, default=480, metavar="PX",
                       help="width of a still in pixels, at most the film's (default 480)")
        c.add_argument("-o", "--output", metavar="FILE",
                       help="where the sheet goes (default contact.png beside the film)")
        c.add_argument("--force", action="store_true",
                       help="build the clips again, even when their key did not change")
        _clips_arg(c)

        n = _parser(
            actions, "lengths", help="planned and measured length per shot, and chapters",
            description="Print each shot's planned length (from the timeline) and its "
                        "measured length (from its finished clip of the last build; - when "
                        "none), the film's, and each chapter's start and length. Nothing is "
                        "built.")
        _film_arg(n)
        n.add_argument("--clips", metavar="DIR",
                       help="folder of the clips (default clips/ beside the film file)")

        t = _parser(
            actions, "srt", help="write the captions as a subtitle file",
            description="Write the captions as SubRip subtitles, at their film times, with "
                        "maths between $ as plain text. Nothing is built.")
        _film_arg(t)
        t.add_argument("-o", "--output", metavar="FILE",
                       help="where the subtitles go (default film.srt beside the film)")

        h = _parser(
            actions, "chapters", help="print the chapters as YouTube timestamps",
            description="Print the chapters as chapters.txt holds them, one '0:00 Title' "
                        "line each, for a YouTube description; what YouTube would refuse "
                        "is noted on stderr. Nothing is built.")
        _film_arg(h)
        h.add_argument("-o", "--output", metavar="FILE", help="write to FILE instead of printing")

        m = _parser(
            actions, "template", help="write a commented film file with the defaults",
            description="Print (or write with -o) a film file with every key at its "
                        "default, each with a comment, and one frames shot.")
        m.add_argument("name", nargs="?", default="my_shot",
                       help="the shot's name; its frames are in frames/NAME (default my_shot)")
        m.add_argument("--fps", type=int, default=24, metavar="N",
                       help="frames a second of the film (default 24)")
        m.add_argument("-o", "--output", metavar="FILE",
                       help="write to FILE instead of printing").completer = paths((".yml", ".yaml"))
        m.add_argument("--force", action="store_true", help="overwrite FILE if it exists")
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

    def do_check(self, args, ctx):
        from flowreel.film.check import contact
        if args.columns < 1 or args.width < 2:
            raise CommandError("--columns must be at least 1 and --width at least 2")
        start = time.perf_counter()
        path = contact(args.film, args.at, args.output, columns=args.columns,
                       width=args.width, folder=args.clips, force=args.force,
                       panels={"jobs": args.jobs})
        ctx.out(f"wrote {path} in {time.perf_counter() - start:.1f} s")
        return 0

    def do_lengths(self, args, ctx):
        from flowreel.film.build import lengths
        for line in lengths(args.film, folder=args.clips).table():
            ctx.out(line)
        return 0

    def do_srt(self, args, ctx):
        from flowreel.film import load, timeline
        from flowreel.film.check import srt
        line = timeline(load(args.film))
        if not line.captions:
            raise CommandError("the film has no captions")
        path = srt(line, args.output)
        ctx.out(f"wrote {path}: {len(line.captions)} captions")
        return 0

    def do_chapters(self, args, ctx):
        from flowreel.film import load, timeline
        from flowreel.film.chapters import youtube_notes, youtube_text
        chapters = timeline(load(args.film)).chapters
        if not chapters:
            raise CommandError("the film has no chapters (a shot's 'chapter: TITLE')")
        text = youtube_text(chapters)
        for note in youtube_notes(chapters):
            ctx.warn(note)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            ctx.out(f"wrote {args.output}: {len(chapters)} chapters")
        else:
            ctx.out(text, end="")
        return 0

    def do_template(self, args, ctx):
        from flowreel.film.template import template
        if args.fps < 1:
            raise CommandError("--fps must be at least 1")
        text = template(args.name, args.fps)
        if not args.output:
            ctx.out(text, end="")
            return 0
        path = Path(args.output)
        if path.exists() and not args.force:
            raise CommandError(f"{path} exists (use --force to overwrite)")
        path.write_text(text)
        ctx.out(f"wrote {path}")
        return 0
