"""A tiny generated film built end to end (plan Section 16): three shots of 10 frames, two
captions, a freeze, a generated tone and chapters. Lengths, caption timing, audio
length, preview size and chapters are measured on the built files; caches rebuild what
changed and nothing else."""
import json
import subprocess

import numpy as np
import pytest
import yaml
from PIL import Image

from flowreel.film import ffmpeg as ff
from flowreel.film.build import build

from film_project import SIZE, decode, need_ffmpeg

FPS = 24
RED = {"place": "centre", "size": 40, "colour": "#ff0000", "shadow": False, "fade": 0.1}
SHOTS = [
    {"name": "a", "frames": "a", "rate": {"fps": 8, "to_output": "interpolate"},
     "chapter": "Start", "text": [{**RED, "lines": ["one"], "at": [0.25, 1.0]}]},
    {"name": "b", "frames": "b", "rate": {"fps": 8, "to_output": "repeat"}, "chapter": "Middle",
     "freezes": [{"at": 0.5, "hold": 0.5}],
     "text": [{**RED, "lines": ["two"], "at": [1.25, 1.75]}]},
    {"name": "c", "frames": "c", "rate": {"fps": 8, "to_output": "blend"}, "fade": [0, 0.5],
     "chapter": {"title": "End", "at": 0.25}},
]
# a: 10 / 8 = 1.25 s; b: 1.25 + 0.5 freeze = 1.75 s; c: 1.25 s.
LENGTHS = {"a": 1.25, "b": 1.75, "c": 1.25}
TOTAL = 4.25


def grey_frames(folder, n=10, base=40):
    """``n`` grey frames, each a different level, so frames can be told apart and no
    pixel looks like the red captions."""
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.new("RGB", SIZE, (base + 12 * i,) * 3).save(folder / f"frame_{i:05d}.png")


def write(folder, shots=SHOTS, **top):
    data = {"fps": FPS, "size": list(SIZE), "shots": shots,
            "audio": {"file": "tone.wav", "start": 0.5, "fade": [0.25, 0.5]}, **top}
    path = folder / "film.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def make(folder):
    for name, base in (("a", 30), ("b", 60), ("c", 90)):
        grey_frames(folder / name, base=base)
    ff.run("-f", "lavfi", "-i", "sine=frequency=440:duration=3:sample_rate=48000",
           "-af", "volume=4", folder / "tone.wav")
    return write(folder)


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    need_ffmpeg()
    folder = tmp_path_factory.mktemp("tiny")
    built = build(make(folder), preview=46)
    return folder, built


def red(frame) -> float:
    f = frame.astype(int)
    return float(((f[..., 0] > 180) & (f[..., 1] < 90) & (f[..., 2] < 90)).mean())


def test_lengths_planned_and_measured(tiny):
    _, built = tiny
    assert {s.name: s.planned for s in built.shots} == LENGTHS
    for s in built.shots:
        assert abs(s.measured - s.planned) < 1e-3, s
    assert built.planned == TOTAL and abs(built.measured - TOTAL) < 1e-3
    assert ff.frame_count(built.output) == TOTAL * FPS


def test_captions_show_at_their_film_times(tiny):
    """One from 0.25 to 1.0 s; two at 1.25 to 1.75 s of b, after its freeze: film 2.5 to
    3.0 s."""
    _, built = tiny
    shown = [red(f) > 0.002 for f in decode(built.output)]
    on = [k for k, s in enumerate(shown) if s]
    first = [k for k in on if k < 30]
    second = [k for k in on if k >= 30]
    assert 6 <= first[0] <= 8 and 22 <= first[-1] <= 24
    assert 60 <= second[0] <= 62 and 70 <= second[-1] <= 72
    assert all(shown[k] for k in range(9, 22)) and all(shown[k] for k in range(63, 70))


def test_the_freeze_holds_one_frame(tiny):
    """b starts at 1.25 s (film frame 30) and repeats each of its frames 3 times; its
    frame 4 shows from 0.5 s in (frame 42), for its own step and the 0.5 s freeze: film
    frames 42 to 56 are the same picture."""
    _, built = tiny
    p = decode(built.output).astype(int)[:, 5, 5, 0]
    held = p[42:57]
    assert held.max() - held.min() <= 1
    assert abs(held[0] - (60 + 12 * 4)) <= 3
    assert p[41] < held[0] - 6 and p[57] > held[0] + 6       # frames 3 before, 5 after


def test_sound_is_as_long_as_the_picture(tiny):
    _, built = tiny
    audio = float(ff.probe(built.output, "stream=duration", stream="a:0"))
    assert abs(audio - TOTAL) < 0.03
    assert any("tone.wav: 0.50 to 3.50 s" in n for n in built.notes)


def test_preview_size(tiny):
    _, built = tiny
    assert built.preview.name == "film_46p.mp4"
    assert ff.probe(built.preview, "stream=width,height").split() == ["82", "46"]
    assert ff.frame_count(built.preview) == TOTAL * FPS


def test_chapters_read_back(tiny):
    _, built = tiny
    for path in (built.output, built.preview):
        done = subprocess.run([str(ff.find().ffprobe), "-v", "error", "-show_chapters", "-of",
                               "json", str(path)], capture_output=True, text=True, check=True)
        found = [(c["tags"]["title"], round(float(c["start_time"]), 3),
                  round(float(c["end_time"]), 3)) for c in json.loads(done.stdout)["chapters"]]
        assert found == [("Start", 0.0, 1.25), ("Middle", 1.25, 3.25), ("End", 3.25, 4.25)]
    assert built.chapters.read_text() == "0:00 Start\n0:01 Middle\n0:03 End\n"


def test_srt(tiny):
    _, built = tiny
    assert built.srt.read_text(encoding="utf-8") == (
        "1\n00:00:00,250 --> 00:00:01,000\none\n\n"
        "2\n00:00:02,500 --> 00:00:03,000\ntwo\n")


# -- caches ----------------------------------------------------------------------------

def rebuilt(built) -> list[str]:
    return [s.name for s in built.shots if s.built]


def clips(folder) -> dict[str, str]:
    return {p.name.rsplit("_", 1)[0]: p.name for p in (folder / "clips").glob("*.mp4")}


def test_caches_rebuild_what_changed_and_nothing_else(tmp_path):
    need_ffmpeg()
    path = make(tmp_path)
    assert rebuilt(build(path)) == ["a", "b", "c"]
    before = clips(tmp_path)
    assert rebuilt(build(path)) == []                         # kept, key for key

    # a caption's words: b's finished clip only; its base clip is kept
    shots = yaml.safe_load(path.read_text())["shots"]
    shots[1]["text"][0]["lines"] = ["TWO"]
    write(tmp_path, shots)
    assert rebuilt(build(path)) == ["b"]
    after = clips(tmp_path)
    assert after["base_b"] == before["base_b"] and after["shot_b"] != before["shot_b"]

    # a frame redrawn: c's base and finished clips
    Image.new("RGB", SIZE, (200, 200, 200)).save(tmp_path / "c" / "frame_00003.png")
    assert rebuilt(build(path)) == ["c"]
    assert clips(tmp_path)["base_c"] != after["base_c"]

    # a rate: a's base clip again
    shots[0]["rate"]["to_output"] = "repeat"
    write(tmp_path, shots)
    assert rebuilt(build(path)) == ["a"]

    # sound, chapters, mute and a preview change no clip
    shots[2]["chapter"] = "Finish"
    write(tmp_path, shots, audio={"file": "tone.wav", "volume": 0.3})
    built = build(path, preview=46)
    assert rebuilt(built) == [] and built.chapters.read_text().endswith("0:03 Finish\n")
    assert rebuilt(build(path, mute=True)) == []

    # force rebuilds every clip
    assert rebuilt(build(path, force=True)) == ["a", "b", "c"]


def test_the_film_is_rewritten_even_when_every_clip_is_kept(tmp_path):
    """The join always runs, so the sound or chapters can change on their own."""
    need_ffmpeg()
    path = make(tmp_path)
    build(path)
    write(tmp_path, SHOTS, audio={"file": "tone.wav", "volume": 0.0})
    built = build(path)
    samples = subprocess.run([str(ff.find().ffmpeg), "-v", "error", "-i", str(built.output),
                              "-map", "0:a", "-f", "f32le", "-"], capture_output=True,
                             check=True).stdout
    assert float(np.abs(np.frombuffer(samples, np.float32)).max()) == 0.0
