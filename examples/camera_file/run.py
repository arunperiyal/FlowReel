"""Build a cameras.yml from code: an imported ParaView view, an orbit and an eased track.

Usage: python run.py [DIR]   (default ./camera_file_example)

Needs no data and draws nothing. It writes DIR/trace.py, a stand-in for a ParaView trace
(in practice saved from ParaView), imports its camera as the view ``wide``, adds an orbit
of a quarter turn round the point it looks at, and a track that holds on ``wide`` for a
second and then eases into the orbit's first view. All of it goes to DIR/cameras.yml,
which a shot then uses with ``camera: {track: intro}`` or ``camera: {track: turn}``.
"""
import sys
from pathlib import Path

from flowreel.scene.camera_file import update_cameras
from flowreel.scene.camera_import import import_view
from flowreel.scene.camera_path import build_track, load_tracks
from flowreel.scene.orbit import orbit
from flowreel.scene.views import load_views

TRACE = """\
renderView1 = GetActiveViewOrCreate('RenderView')
renderView1.CameraPosition = [-19.0, 13.0, -5.0]
renderView1.CameraFocalPoint = [6.0, 0.0, 8.5]
renderView1.CameraViewUp = [0.0, 1.0, 0.0]
renderView1.CameraViewAngle = 30.0
"""


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "trace.py").write_text(TRACE)
    wide = import_view(folder / "trace.py", "wide")
    path = update_cameras(folder / "cameras.yml", {"wide": wide})

    views, turn = orbit(wide.focal, radius=12, frames=120, azimuth=180, span=90,
                        elevation=(20, 35), name="turn")
    update_cameras(path, views, {"turn": turn})

    views = load_views(path)
    intro = build_track(views, [(0, "wide", "hold"), (24, "wide"), (72, "turn_00")])
    update_cameras(path, tracks={"intro": intro})

    tracks = load_tracks(path, load_views(path))
    print(f"wrote {path.name}: {len(load_views(path))} views, tracks {', '.join(tracks)}")
    print("intro at frame 48:", ", ".join(f"{x:.2f}" for x in tracks["intro"].at(48).position))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("camera_file_example"))
