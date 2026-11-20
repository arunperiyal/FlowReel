"""The film build: finished clips joined without re-encoding, lengths planned and
measured."""
import pytest

from flowreel.film import ffmpeg as ff
from flowreel.film.build import build

from film_project import decode, film_file, frames, mean_colour, need_ffmpeg


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def two_shots(tmp_path, **top):
    frames(tmp_path / "a", 12)
    frames(tmp_path / "b", 6, start=20)
    return film_file(tmp_path, [{"name": "a", "frames": "a"},
                                {"name": "b", "frames": "b", "rate": {"fps": 12, "to_output": "repeat"}}],
                     **top)


def test_the_film_is_its_clips_joined_in_order(tmp_path):
    built = build(two_shots(tmp_path))
    assert built.output == tmp_path / "film.mp4"
    assert [(s.name, s.planned) for s in built.shots] == [("a", 0.5), ("b", 0.5)]
    assert all(abs(s.measured - s.planned) < 1e-3 and s.built for s in built.shots)
    assert ff.frame_count(built.output) == 24
    assert abs(ff.length(built.output) - 1.0) < 1e-3
    p = decode(built.output)
    assert abs(mean_colour(p[5]) - mean_colour(decode(tmp_path / "a" / "frame_00005.png")[0])).max() < 6
    assert abs(mean_colour(p[12]) - mean_colour(decode(tmp_path / "b" / "frame_00000.png")[0])).max() < 6


def test_the_join_copies_the_clips_picture(tmp_path):
    """Not re-encoded: the film's video packets are the clips' own. (Each clip's first
    packet carries that clip's parameter sets in front, written in by the join.)"""
    import hashlib
    import subprocess

    def packets(path):
        done = subprocess.run([str(ff.find().ffmpeg), "-v", "error", "-i", str(path), "-map",
                               "0:v", "-c", "copy", "-f", "framemd5", "-"],
                              capture_output=True, text=True, check=True)
        return [line.split(",")[-1].strip() for line in done.stdout.splitlines()
                if not line.startswith("#")]
    built = build(two_shots(tmp_path))
    clips = sorted((tmp_path / "clips").glob("shot_*.mp4"))
    by_name = {c.name.split("_")[1]: c for c in clips}
    a, b = packets(by_name["a"]), packets(by_name["b"])
    joined = packets(built.output)
    assert len(joined) == len(a) + len(b) == 24
    assert joined[1:12] == a[1:] and joined[13:] == b[1:]


def test_a_second_build_keeps_every_clip(tmp_path):
    path = two_shots(tmp_path)
    build(path)
    again = build(path)
    assert not any(s.built for s in again.shots)
    lines = again.table()
    assert lines[0].split() == ["shot", "planned", "measured"]
    assert lines[1].split()[:5] == ["a", "0.50", "s", "0.50", "s"] and lines[1].endswith("kept")
    assert lines[3].startswith("film") and lines[3].endswith("film.mp4")
