"""examples/camera_file/run.py: a cameras.yml built from an import, an orbit and a track."""
import subprocess
import sys
from pathlib import Path

from flowreel.scene.camera_path import load_tracks
from flowreel.scene.views import load_views

RUN = Path(__file__).parent.parent / "examples" / "camera_file" / "run.py"


def test_example_writes_cameras(tmp_path):
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    lines = done.stdout.splitlines()
    assert lines[0] == "wrote cameras.yml: 20 views, tracks turn, intro"
    path = tmp_path / "ex" / "cameras.yml"
    views = load_views(path)
    tracks = load_tracks(path, views)
    assert views["wide"].position == (-19, 13, -5)
    assert tracks["intro"].at(20).position == views["wide"].position     # held
    assert tracks["intro"].at(72) == views["turn_00"]                   # the last key
    assert (tmp_path / "ex" / "cameras.yml.bak").exists()
