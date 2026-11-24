"""``flowreel scene``: a film's scenes listed, and a scene seen before the film is built.

``scene list`` prints each scene's place in the film, length and boxes; ``scene
preview`` draws stills of one scene (the frames as the build draws them, without the
scene's fades) to look at its layout and text without encoding anything; ``scene
design`` opens a window to draw, move, resize, name and fill its boxes
(:mod:`flowreel.editor.design_window`).
"""
from __future__ import annotations

import argparse
import textwrap
import time
from pathlib import Path

from shellkit import BaseCommand, CommandError

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "scene": """examples:
  flowreel scene list
  flowreel scene preview opening --at 2.5
  flowreel scene design compare

Reference: docs/guide/film/film.md and docs/guide/commands.md.""",
    "list": """examples:
  flowreel scene list                        the project's film.yml
  flowreel scene list films/short.yml""",
    "design": """examples:
  flowreel scene design opening              a window on the scene's layout
  flowreel scene design compare --grid 10    snap to a 10-pixel grid (0: none)""",
    "preview": """examples:
  flowreel scene preview opening             stills at the start, middle and end
  flowreel scene preview compare --at 1 4.5 9 -o previews/
  flowreel scene preview compare --every 2   a still every 2 seconds""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _film_arg(parser):
    parser.add_argument("--film", metavar="FILM", default=None,
                        help="the film file (default the project's film.yml)")


class SceneCommand(BaseCommand):
    """The ``scene`` command group."""

    name = "scene"
    description = "A film's scenes: list them, preview one"
    category = "Film"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["scene"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="scene_cmd", metavar="<action>")
        lst = _parser(actions, "list", help="each scene: start, length, boxes",
                      description="List the scenes of a film of scenes: where each starts in "
                                  "the film, how long it lasts (its seconds, or its main box's "
                                  "frames), its boxes and its chapter. A scene whose shot has "
                                  "no frames yet is listed with its length unknown.")
        lst.add_argument("film_file", nargs="?", metavar="FILM",
                         help="the film file (default the project's film.yml)")
        pre = _parser(actions, "preview", help="stills of a scene, as the build draws them",
                      description="Draw stills of one scene into OUT/scenes/NAME/at_S.png "
                                  "(default frames/ at the project root): its boxes at those "
                                  "seconds, as the build draws them, without the scene's fades. "
                                  "Shot boxes need their frames; a held last frame shows once "
                                  "its scene's clip is built.")
        pre.add_argument("scene", metavar="NAME", help="the scene")
        when = pre.add_mutually_exclusive_group()
        when.add_argument("--at", type=float, nargs="+", metavar="S",
                          help="seconds into the scene (default its start, middle and end)")
        when.add_argument("--every", type=float, metavar="S", help="a still every S seconds")
        pre.add_argument("-o", "--out", metavar="DIR",
                         help="folder of the stills (default frames/scenes/NAME)")
        _film_arg(pre)
        des = _parser(actions, "design", help="a window to draw and fill a scene's boxes",
                      description="Open a window on one scene's layout, drawn as the build "
                                  "draws it at the Time slider's moment. Drag on empty space "
                                  "to draw a box, drag a box to move it, a corner to resize "
                                  "it; edges snap to other boxes, the frame and the grid. The "
                                  "panel names and fills the selected box. Every change is "
                                  "checked and written at once: to layouts/NAME.yml, or to the "
                                  "scene's layout block in film.yml. Keys: u undo, delete "
                                  "remove, g grid, t the next second.")
        des.add_argument("scene", metavar="NAME", help="the scene")
        des.add_argument("--grid", type=float, default=20.0, metavar="PX",
                         help="snap to a grid of PX pixels (default 20; 0 for none)")
        _film_arg(des)
        return p

    def execute(self, args, ctx):
        from flowreel.film.ffmpeg import FfmpegError
        if not args.scene_cmd:
            ctx.error("give an action: flowreel scene --help")
            return 2
        try:
            return getattr(self, "do_" + args.scene_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename or exc}") from None
        except KeyError as exc:
            raise CommandError(str(exc.args[0]) if exc.args else str(exc)) from None
        except (ValueError, FfmpegError) as exc:
            raise CommandError(str(exc)) from None

    def _film(self, ctx, given):
        from flowreel.cli.project import project_root
        from flowreel.film.model import load
        path = Path(given) if given else project_root(ctx) / "film.yml"
        if not path.is_file():
            raise CommandError(f"no film file {path} (flowreel film template)")
        return load(path)

    def do_list(self, args, ctx):
        from flowreel.film.scene_build import EPS, scene_length
        film = self._film(ctx, args.film_file)
        start, known = 0.0, True
        width = max(len(s.name) for s in film.scenes)
        ctx.out(f"{'scene':{width}s}    start   length  boxes")
        for k, scene in enumerate(film.scenes):
            try:
                length = round(scene_length(scene, film) * film.fps) / film.fps
                text = f"{length:6.2f} s"
            except ValueError as exc:
                length, text, known = None, "     ? s", False
                ctx.warn(str(exc))
            at = f"{start:6.2f} s" if known else "     ? s"
            main = scene.layout.main
            boxes = ", ".join(f"{b.name} ({b.kind}{', main' if b is main else ''})"
                              for b in scene.layout.boxes)
            extra = []
            if scene.layout.file is not None:
                extra.append(f"layout {scene.layout.file.name}")
            if scene.chapter is not None:
                extra.append(f"chapter '{scene.chapter.title}'")
            if scene.cross:
                extra.append(f"cross {scene.cross:g} s")
            ctx.out(f"{scene.name:{width}s}  {at}  {text}  {boxes}"
                    + (f"; {'; '.join(extra)}" if extra else ""))
            if length is not None and known:
                start += length - (scene.cross if k < len(film.scenes) - 1 else 0)
        if known:
            ctx.out(f"{'film':{width}s}  {start + EPS:6.2f} s")
        return 0

    def do_design(self, args, ctx):
        from flowreel.editor.design_window import DesignWindow
        from flowreel.editor.layout_state import DesignState
        film = self._film(ctx, args.film)
        if args.grid < 0:
            raise CommandError("--grid is 0 (none) or more")
        state = DesignState.open(film.file, args.scene, grid=args.grid)
        where = state.layout_file or f"{film.file} (scene {args.scene}'s layout)"
        ctx.out(f"designing scene {args.scene}: changes are written to {where} at once")
        DesignWindow(state).show()
        ctx.out(f"closed: {len(state.boxes)} boxes")
        return 0

    def do_preview(self, args, ctx):
        from flowreel.film.scene_build import SceneBuilder
        from flowreel.project.paths import output
        film = self._film(ctx, args.film)
        scene = film.scene(args.scene)
        builder = SceneBuilder(film)
        placed = builder.plan.placed(scene.name)
        last = (placed.frames - 1) / film.fps
        if args.every is not None:
            if args.every <= 0:
                raise CommandError("--every must be more than 0")
            times = [k * args.every for k in range(int(last / args.every + 1e-9) + 1)]
        else:
            times = args.at if args.at else [0.0, placed.length / 2, last]
        for t in times:
            if not 0 <= t <= placed.length + 1e-9:
                raise CommandError(f"{t:g} s is outside scene {scene.name!r} "
                                   f"(0 to {placed.length:g} s)")
        held = {}
        for b in scene.layout.boxes:
            if b.kind == "last_frame":
                path = builder.folder / f"scene_{b.content.scene}_{builder.key(b.content.scene)}.last.png"
                if path.is_file():
                    held[b.name] = path
                else:
                    ctx.warn(f"box {b.name!r}: scene {b.content.scene!r} is not built yet, so "
                             f"its last frame is not shown (film build --only {b.content.scene})")
        out = Path(args.out) if args.out else output(film.folder, "frames") / "scenes" / scene.name
        out.mkdir(parents=True, exist_ok=True)
        timed = builder._timed(scene)
        start = time.perf_counter()
        try:
            for t in times:
                j = min(round(t * film.fps), placed.frames - 1)
                path = out / f"at_{t:.2f}.png"
                builder.frame(scene.name, j, held, timed).save(path)
                ctx.out(f"  {path.name}")
        finally:
            for pictures in timed.values():
                pictures.close()
        ctx.out(f"{len(times)} stills of {scene.name} in {time.perf_counter() - start:.1f} s "
                f"-> {out}")
        return 0
