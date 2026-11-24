"""``flowreel camera``: pick, make, import and check camera views and tracks.

Each action is a thin layer over a library function: the editor
(:mod:`flowreel.editor`), :func:`~flowreel.scene.camera_path.build_track`,
:func:`~flowreel.scene.orbit.orbit`, :func:`~flowreel.scene.camera_import.import_view`
and :func:`~flowreel.scene.projection.project`. They all read and write one
``cameras.yml``: ``-c FILE``, else the project's, at its root (plan Section 23, question
6). A ``cameras.yml`` left beside a shot below the root is an error that says to move it.
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
import time
from pathlib import Path

from shellkit import BaseCommand, CommandError, add_context_arg, paths

from flowreel.scene.errors import ConfigError

EXAMPLES = {
    "camera": """examples:
  flowreel camera edit wake.yml --track approach     pick views in a window
  flowreel camera orbit turn --target 6 0 9.5 --radius 12 --frames 240 --span 120
  flowreel camera path intro --keys 0:wide:hold 24:wide 72:close
  flowreel camera import state.pvsm wide
  flowreel camera project --track carve --points 6,0.42,0.18
  flowreel camera preview approach wake.yml

Every action reads and writes one cameras.yml: -c FILE, else the project's, at its
root. Reference: docs/guide/commands.md, docs/guide/shots/camera-editor.md.""",
    "edit": """examples:
  flowreel camera edit wake.yml --track approach     a window on the shot's first step
  flowreel camera edit wake.yml --track approach --film film.yml   with the points boxes follow
  flowreel camera edit --vtp wake_vtp --track approach --frames 240 -c cameras.yml
                                                     away from the data (shot render --save-vtp)

keys: s save view, u undo, r replace nearest, p play, n next step""",
    "path": """examples:
  flowreel camera path intro --keys 0:wide 120:close      eased between two views
  flowreel camera path intro --keys 0:wide:hold 24:wide 72:close --path spline
  flowreel camera path intro --keys 0:a 50:b 90:c --ease linear --frames 120""",
    "orbit": """examples:
  flowreel camera orbit turn --target 6 0 9.5 --radius 12 --frames 240
  flowreel camera orbit turn --target 6 0 9.5 --radius 12 --frames 240 --azimuth -30 \\
      --span 120 --elevation 10 35
  flowreel camera orbit riser_turn --shot riser.yml --body riser --station 250 \\
      --radius 8 --frames 240 --span 180 --up 0 1 0 --lead 2""",
    "import": """examples:
  flowreel camera import state.pvsm wide              a ParaView state's camera, as 'wide'
  flowreel camera import trace.py top --index 1       the second render view of a trace
  flowreel camera import cam.yml close                a flexflow camera frame""",
    "project": """examples:
  flowreel camera project --view main --points 6,0.42,0.18 0,0,0
  flowreel camera project --track carve --points 6,0.42,0.18 --frames 0:288:24
  flowreel camera project --track carve --points 6,0.42,0.18 --size 1280 720

In the shell, `use view:main` and --view can be left out.""",
    "preview": """examples:
  flowreel camera preview approach wake.yml           every 4th frame at a quarter size
  flowreel camera preview approach --vtp wake_vtp -c cameras.yml --every 8""",
}


def _parser(actions, name, help, description):
    return actions.add_parser(name, help=help, description=textwrap.fill(description, 78),
                              epilog=EXAMPLES[name],
                              formatter_class=argparse.RawDescriptionHelpFormatter)


def _shot_arg(parser, required=False):
    add_context_arg(parser, "shot", required=required,
                    help="shot file (default: the shot set with use shot:FILE)"
                    ).completer = paths((".yml", ".yaml"))


def _cameras_arg(parser):
    parser.add_argument("-c", "--cameras", metavar="FILE",
                        help="cameras.yml to read and write (default: the project's, at "
                             "its root)")


def cameras_path(args) -> Path:
    """The ``cameras.yml`` an action uses (see the module)."""
    from flowreel.project.paths import CAMERAS_FILE, cameras_file
    if getattr(args, "cameras", None):
        return Path(args.cameras)
    shot = getattr(args, "shot", None)
    if shot:
        return cameras_file(shot)
    root = getattr(args, "root", None)
    return Path(root) / CAMERAS_FILE if root else Path(CAMERAS_FILE)


def _point(text: str) -> tuple[float, float, float]:
    try:
        x, y, z = (float(v) for v in text.split(","))
    except ValueError:
        raise CommandError(f"--points: {text!r} is not x,y,z") from None
    return (x, y, z)


class CameraCommand(BaseCommand):
    """The ``camera`` command group."""

    name = "camera"
    description = "Pick, make, import and check camera views and tracks"
    category = "Cameras"

    def setup_parser(self, subparsers):
        p = subparsers.add_parser(self.name, help=self.description,
                                  description=self.description, epilog=EXAMPLES["camera"],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        actions = p.add_subparsers(dest="camera_cmd", metavar="<action>")

        e = _parser(actions, "edit", help="pick views into a track in a window",
                    description="Open the camera editor on the shot's scene: move the camera, "
                                "set the Frame slider, press s to save the view as a key of "
                                "the track. Every change is written to cameras.yml at once.")
        _shot_arg(e)
        e.add_argument("--track", required=True, metavar="NAME", help="the track to make or extend")
        e.add_argument("--frames", type=int, metavar="N",
                       help="the track's length (default: the shot's frames; needed with --vtp "
                            "and no shot)")
        e.add_argument("--vtp", metavar="DIR",
                       help="open surfaces saved by 'shot render --save-vtp DIR' instead of the data")
        e.add_argument("--film", metavar="FILE",
                       help="mark the points in the model that this film's captions point at")
        e.add_argument("--spline", action="store_true", help="write the track with path: spline")
        e.add_argument("--size", type=int, nargs=2, default=(1280, 720), metavar=("W", "H"),
                       help="the window's size (default 1280 720)")
        _cameras_arg(e)

        t = _parser(actions, "path", help="write a track from keys",
                    description="Write a camera track from keys FRAME:VIEW, or FRAME:VIEW:EASE "
                                "for the segment from that key to the next, with views of "
                                "cameras.yml.")
        t.add_argument("name", metavar="NAME", help="the track's name")
        t.add_argument("--keys", nargs="+", required=True, metavar="F:VIEW[:EASE]",
                       help="the keys, frames increasing")
        t.add_argument("--path", choices=("linear", "spline"), default="linear",
                       help="through the keys: linear (default) or spline")
        t.add_argument("--ease", default="smooth", metavar="E",
                       help="the segments' easing unless a key gives one (default smooth)")
        t.add_argument("--frames", type=int, metavar="N", help="the track's length")
        _cameras_arg(t)

        o = _parser(actions, "orbit", help="write an arc of views round a point or a body",
                    description="Write views and a track that circle a target: a point "
                                "(--target), or a body's centre at a station along its axis "
                                "(--body, --station, with the shot's source). Angles in degrees.")
        o.add_argument("name", metavar="NAME", help="the track's name (views NAME_00, NAME_01, ...)")
        o.add_argument("--radius", type=float, required=True, metavar="R",
                       help="the camera's distance from the target")
        o.add_argument("--frames", type=int, required=True, metavar="N", help="the track's length")
        o.add_argument("--target", type=float, nargs=3, metavar=("X", "Y", "Z"), help="a point")
        o.add_argument("--body", metavar="NAME", help="a body of the shot's source ('' for the one)")
        o.add_argument("--station", type=float, metavar="S", help="where along the body's axis")
        o.add_argument("--step", type=int, metavar="N", help="the body at this step (default the first)")
        o.add_argument("--shot", metavar="FILE", help="the shot whose source has the body")
        o.add_argument("--azimuth", type=float, default=0.0, metavar="A", help="where it starts (0)")
        o.add_argument("--span", type=float, default=360.0, metavar="S",
                       help="degrees turned, + anticlockwise seen from the axis tip (360)")
        o.add_argument("--elevation", type=float, nargs="+", default=[0.0], metavar="E",
                       help="above the plane across the axis: one angle, or from and to (0)")
        o.add_argument("--axis", default=None, metavar="x|y|z",
                       help="turn about this axis (default y, or with --station the body's "
                            "axis; the station is always along the body's axis)")
        o.add_argument("--up", type=float, nargs=3, metavar=("X", "Y", "Z"),
                       help="the camera's up (default the axis)")
        o.add_argument("--lead", type=float, default=0.0, metavar="L",
                       help="focal point moved this far along the axis (0)")
        o.add_argument("--view-angle", type=float, default=30.0, metavar="DEG", help="(30)")
        o.add_argument("--ease", default="smooth", metavar="E", help="over the whole turn (smooth)")
        _cameras_arg(o)

        i = _parser(actions, "import", help="a view from ParaView or flexflow",
                    description="Add a view to cameras.yml from a ParaView state (.pvsm), a "
                                "ParaView Python state or trace (.py), or a flexflow camera "
                                "frame or another cameras.yml (.yml).")
        i.add_argument("file", metavar="FILE", help="the file holding the camera")
        i.add_argument("view_name", nargs="?", default="main", metavar="NAME",
                       help="the view's name in cameras.yml (default main)")
        i.add_argument("--index", type=int, default=0, metavar="I",
                       help="which render view of a ParaView file (0, the first)")
        i.add_argument("--view", metavar="V", help="which view of a cameras.yml")
        i.add_argument("--force", action="store_true", help="replace a view of the same name")
        _cameras_arg(i)

        r = _parser(actions, "project", help="screen positions of model points",
                    description="Print where model points land on the screen, in pixels from "
                                "the upper left (y down), for a view or for every frame of a "
                                "track: for placing captions and arrows.")
        add_context_arg(r, "view", "--view", required=False, metavar="V",
                        resolve=_context_view,
                        help="a view (default: the view set with use view:NAME, unless "
                             "--track is given)")
        r.add_argument("--track", metavar="T", help="a track, frame by frame")
        r.add_argument("--points", nargs="+", required=True, metavar="X,Y,Z", help="model points")
        r.add_argument("--size", type=int, nargs=2, default=(1920, 1080), metavar=("W", "H"),
                       help="the picture's size (default 1920 1080)")
        r.add_argument("--frames", metavar="SPEC", help="a track's frames: A:B:E or a list")
        _cameras_arg(r)

        v = _parser(actions, "preview", help="small frames of a track, quickly",
                    description="Draw a track's frames small over one scene (the shot's first "
                                "step, or saved surfaces), to see the camera move without "
                                "rendering the shot.")
        v.add_argument("track", metavar="TRACK", help="the track")
        _shot_arg(v)
        v.add_argument("--vtp", metavar="DIR", help="surfaces saved by 'shot render --save-vtp'")
        v.add_argument("--every", type=int, default=4, metavar="N", help="every Nth frame (4)")
        v.add_argument("--scale", type=float, default=0.25, metavar="S",
                       help="the shot's size times S (0.25; 1920x1080 without a shot)")
        v.add_argument("-o", "--out", metavar="DIR",
                       help="frames go to DIR/<track>@preview/ (default frames/ at the "
                            "project root)")
        _cameras_arg(v)
        return p

    def execute(self, args, ctx):
        if not args.camera_cmd:
            ctx.error("give an action: flowreel camera --help")
            return 2
        from flowreel.cli.project import project_root
        root = project_root(ctx, getattr(args, "shot", None), getattr(args, "cameras", None))
        args.root = str(root)
        if getattr(args, "out", "") is None:
            args.out = str(root / "frames")
        try:
            return getattr(self, "do_" + args.camera_cmd)(args, ctx)
        except ConfigError as exc:
            raise CommandError(str(exc)) from None
        except FileNotFoundError as exc:
            raise CommandError(f"no such file: {exc.filename or exc}") from None

    # -- edit -----------------------------------------------------------------------

    def do_edit(self, args, ctx):
        from flowreel.editor.state import EditorState
        from flowreel.editor.window import EditorWindow
        if not args.shot and not args.vtp:
            raise CommandError("give a shot (or use shot:FILE), or --vtp DIR")
        if args.frames is not None and args.frames < 1:
            raise CommandError("--frames must be at least 1")
        scene = None
        if args.vtp:
            from flowreel.editor.surfaces import SavedScenes
            scenes = SavedScenes(args.vtp)
        else:
            from flowreel.editor.scenes import ShotScenes
            from flowreel.scene.rendering import Scene
            scene = Scene.make(args.shot)
            scenes = ShotScenes(scene)
        frames = args.frames or (scene.plan.n_frames if scene is not None else None)
        if frames is None:
            raise CommandError("--frames N is needed with --vtp and no shot")
        anchors = self._anchors(args, scene)
        if not args.cameras and not args.shot:
            raise CommandError("give -c FILE: with --vtp and no shot there is no cameras.yml "
                               "to go beside")
        if not _display():
            raise CommandError("no display to open the window on: run it where there is one "
                               "(save the surfaces here with 'shot render SHOT --save-vtp DIR', "
                               "copy DIR, and use 'camera edit --vtp DIR' there)")
        path = cameras_path(args)
        state = EditorState.open(path, args.track, frames, scenes.steps,
                                 "spline" if args.spline else "linear",
                                 frame_steps=getattr(scenes, "frame_steps", None))
        window = EditorWindow(state, scenes, size=tuple(args.size), anchors=anchors)
        ctx.out(f"editing track {args.track!r} of {path}; s save, u undo, r replace, "
                "p play, n next step; close the window when done")
        window.show()
        ctx.out(state.status().split("   ")[0] + f" -> {path}")
        return 0

    def _anchors(self, args, scene):
        if not args.film:
            return []
        name = scene.shot.name if scene is not None else None
        from flowreel.film.model import is_scene_film
        from flowreel.yamlfile import read_yaml
        if is_scene_film(read_yaml(args.film)):
            from flowreel.film.boxes import follow_points
            from flowreel.film.model import load as load_scenes
            return follow_points(load_scenes(args.film), name)
        from flowreel.film import load
        from flowreel.film.anchors import anchors_for_frames
        film = load(args.film)
        out = []
        for s in film.shots:
            if s.kind == "frames" and (name is None or Path(s.source).name == name):
                out += [a for a in anchors_for_frames(film, s.source) if a not in out]
        return out

    # -- path, orbit, import ----------------------------------------------------------

    def do_path(self, args, ctx):
        from flowreel.scene.camera_file import update_cameras
        from flowreel.scene.camera_path import build_track
        path = cameras_path(args)
        views = _views(path)
        keys = []
        for text in args.keys:
            bits = text.split(":")
            if len(bits) not in (2, 3):
                raise CommandError(f"--keys: {text!r} is not FRAME:VIEW or FRAME:VIEW:EASE")
            try:
                frame = float(bits[0])
            except ValueError:
                raise CommandError(f"--keys: {bits[0]!r} in {text!r} is not a frame") from None
            keys.append((frame, bits[1], bits[2] if len(bits) == 3 else None))
        if args.frames is not None and args.frames < 1:
            raise CommandError("--frames must be at least 1")
        try:
            track = build_track(views, keys, args.path, args.ease, args.frames)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        update_cameras(path, tracks={args.name: track})
        ctx.out(f"wrote track {args.name!r} ({len(keys)} keys, frames {keys[0][0]:g} to "
                f"{keys[-1][0]:g}) to {path}")
        return 0

    def do_orbit(self, args, ctx):
        from flowreel.scene.camera_file import update_cameras
        from flowreel.scene.orbit import body_target, orbit
        if (args.target is None) == (args.station is None):
            raise CommandError("give --target X Y Z, or --station S (with --body and --shot)")
        axis = args.axis
        if args.target is not None:
            if args.body is not None:
                raise CommandError("--body goes with --station, not --target")
            target = tuple(args.target)
        else:
            if not args.shot:
                raise CommandError("--station needs --shot FILE, whose source has the body")
            source = _shot_source(args.shot)
            try:
                target, body_axis = body_target(source, args.body or None, args.station,
                                                args.step)
            except (LookupError, ValueError) as exc:
                raise CommandError(str(exc.args[0]) if exc.args else str(exc)) from None
            axis = axis or body_axis
        if len(args.elevation) not in (1, 2):
            raise CommandError("--elevation takes one angle, or two (from, to)")
        elevation = args.elevation[0] if len(args.elevation) == 1 else tuple(args.elevation)
        try:
            views, track = orbit(target, args.radius, args.frames, args.azimuth, args.span,
                                 elevation, axis or "y", args.up, args.lead, args.view_angle,
                                 args.ease, args.name)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
        path = update_cameras(cameras_path(args), views, {args.name: track})
        ctx.out(f"wrote track {args.name!r}: {len(views)} views round "
                f"({', '.join(f'{round(x, 4) + 0.0:g}' for x in target)}) over {args.frames} frames "
                f"to {path}")
        return 0

    def do_import(self, args, ctx):
        from flowreel.scene.camera_file import update_cameras
        from flowreel.scene.camera_import import import_view
        path = cameras_path(args)
        if path.exists() and args.view_name in _views(path) and not args.force:
            raise CommandError(f"{path} has a view {args.view_name!r} already "
                               "(use --force to replace it)")
        view = import_view(args.file, args.view_name, args.index, args.view)
        update_cameras(path, {args.view_name: view})
        kind = "parallel" if view.parallel else f"view angle {view.view_angle:g}"
        ctx.out(f"wrote view {args.view_name!r} ({kind}) from {args.file} to {path}")
        return 0

    # -- project and preview ----------------------------------------------------------

    def do_project(self, args, ctx):
        from flowreel.cli.shot import parse_frames
        from flowreel.scene.projection import project
        if (args.view is None) == (args.track is None):
            raise CommandError("give --view V or --track T (or use view:NAME)")
        points = [_point(p) for p in args.points]
        path = cameras_path(args)
        views = _views(path)
        if args.view is not None:
            if args.view not in views:
                raise CommandError(f"no view {args.view!r} in {path} (views: {', '.join(views)})")
            rows = [(None, views[args.view])]
        else:
            from flowreel.scene.camera_path import load_tracks
            tracks = load_tracks(path, views)
            if args.track not in tracks:
                raise CommandError(f"no track {args.track!r} in {path} "
                                   f"(tracks: {', '.join(tracks) or 'none'})")
            track = tracks[args.track]
            n = track.frames or int(track.keys[-1][0]) + 1
            frames = parse_frames(args.frames) if args.frames else range(n)
            rows = [(f, track.at(f)) for f in frames]
        size = tuple(args.size)
        header = ("frame  " if args.track else "") + "  ".join(
            f"{p:>22}" for p in (",".join(f"{v:g}" for v in pt) for pt in points))
        ctx.out(header)
        for frame, view in rows:
            cells = []
            for x, y, depth in project(view, points, size):
                cells.append(f"{'behind':>22}" if x != x else f"{f'({x:.1f}, {y:.1f})':>22}")
            ctx.out((f"{frame:>5}  " if frame is not None else "") + "  ".join(cells))
        return 0

    def do_preview(self, args, ctx):
        import numpy as np
        import pyvista as pv
        from PIL import Image
        from flowreel.scene.camera_path import load_tracks
        if args.every < 1 or args.scale <= 0:
            raise CommandError("--every must be at least 1 and --scale positive")
        if not args.shot and not args.vtp:
            raise CommandError("give a shot (or use shot:FILE), or --vtp DIR")
        if args.vtp:
            from flowreel.editor.surfaces import SavedScenes
            scenes, full = SavedScenes(args.vtp), (1920, 1080)
        else:
            from flowreel.editor.scenes import ShotScenes
            from flowreel.scene.rendering import Scene
            scene = Scene.make(args.shot)
            scenes, full = ShotScenes(scene), scene.shot.size
        if args.shot and args.vtp:
            from flowreel.scene.shot import load
            full = load(args.shot).size
        path = cameras_path(args)
        views = _views(path)
        tracks = load_tracks(path, views)
        if args.track not in tracks:
            raise CommandError(f"no track {args.track!r} in {path} (tracks: {', '.join(tracks) or 'none'})")
        track = tracks[args.track]
        n = track.frames or int(track.keys[-1][0]) + 1
        size = (max(2, round(full[0] * args.scale)), max(2, round(full[1] * args.scale)))
        folder = Path(args.out) / f"{args.track}@preview"
        folder.mkdir(parents=True, exist_ok=True)
        start = time.perf_counter()
        plotter = pv.Plotter(off_screen=True, window_size=list(size))
        try:
            if scenes.background is not None:
                plotter.set_background(scenes.background)
            scenes.build(plotter, scenes.steps[0])
            frames = sorted(set(range(0, n, args.every)) | {n - 1})
            for f in frames:
                track.at(f).apply(plotter.camera)
                plotter.renderer.ResetCameraClippingRange()
                plotter.render()                 # screenshot() alone shows the last render
                picture = np.asarray(plotter.screenshot(return_img=True))[:, :, :3]
                Image.fromarray(picture).save(folder / f"frame_{f:05d}.png")
        finally:
            plotter.close()
        ctx.out(f"{len(frames)} frames of {args.track!r} at {size[0]}x{size[1]} in "
                f"{time.perf_counter() - start:.1f} s -> {folder}")
        return 0


def _shot_source(path):
    """The source of the shot at ``path``, seen through its project's bodies, without
    making the shot's scene: its camera may be the very track being made."""
    from flowreel.project import project_for
    from flowreel.project.names import declare
    from flowreel.scene.rendering import open_source
    from flowreel.scene.shot import load
    shot = load(path)
    return declare(open_source(shot), project_for(shot.file))


def _context_view(store, namespace):
    """The ``view`` context, unless ``--track`` was typed (it then wins)."""
    return None if getattr(namespace, "track", None) is not None else store.get("view")


def _views(path: Path) -> dict:
    from flowreel.scene.views import load_views
    if not path.exists():
        raise CommandError(f"no {path}: make views first (camera edit, camera import or "
                           "camera orbit), or give -c FILE")
    return load_views(path)


def _display() -> bool:
    """Whether a window can be shown here."""
    if sys.platform != "linux":
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
