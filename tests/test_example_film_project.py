"""examples/film_project/run.py: a silent film with a card, a layout shot with live
plots and a freeze, a hold and a text watermark, on generated data."""
import subprocess
import sys
from pathlib import Path

from flowreel.film import ffmpeg as ff
from film_project import need_ffmpeg

RUN = Path(__file__).parent.parent / "examples" / "film_project" / "run.py"


def test_example_builds_the_project(tmp_path):
    need_ffmpeg()
    done = subprocess.run([sys.executable, str(RUN), str(tmp_path / "ex")], capture_output=True,
                          text=True, timeout=900)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines() == [
        "shot     planned  measured",
        "opening    2.00 s    2.00 s  built",
        "compare    4.50 s    4.50 s  built",
        "end        2.00 s    2.00 s  built",
        "film       8.50 s    8.50 s  film.mp4",
        "srt film.srt"]
    film = tmp_path / "ex" / "film.mp4"
    assert ff.frame_count(film) == 8.5 * 24
    assert ff.probe(film, "stream=codec_type", stream="a") == ""          # silent
    layouts = tmp_path / "ex" / "clips" / "layouts"
    assert len(list((layouts / "compare_flow").glob("frame_*.png"))) == 24   # at the wakes' rate
    # the plots once per output frame: 24 wake frames and a 1.5 s freeze at 8 fps, x 3
    assert len(list((layouts / "plots_output").glob("frame_*.png"))) == (24 + 12) * 3
