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


# -- audio ---------------------------------------------------------------------------

def tone(path, seconds, freq=440):
    """A generated sine tone of ``seconds``, peaking at 0.5 of full scale."""
    ff.run("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
           "-af", "volume=4", "-c:a", "pcm_s16le", path)      # sine is 1/8: 0.5
    return path


def sound(path):
    """The film's sound as float samples, mono, 48 kHz."""
    import subprocess
    import numpy as np
    done = subprocess.run([str(ff.find().ffmpeg), "-v", "error", "-i", str(path), "-map", "0:a",
                           "-ac", "1", "-ar", "48000", "-f", "f32le", "-"],
                          capture_output=True, check=True)
    return np.frombuffer(done.stdout, np.float32)


def loudness(samples, t, width=0.05):
    """Peak level around ``t`` seconds."""
    a, b = int((t - width) * 48000), int((t + width) * 48000)
    return float(abs(samples[max(a, 0):b]).max())


def audio_length(path) -> float:
    return float(ff.probe(path, "stream=duration", stream="a:0"))


def test_a_track_plays_under_the_picture_cut_to_its_length(tmp_path):
    tone(tmp_path / "tone.wav", 3.0)
    built = build(two_shots(tmp_path, audio={"file": "tone.wav", "volume": 0.5}))
    assert abs(audio_length(built.output) - 1.0) < 0.03
    assert abs(ff.length(built.output) - 1.0) < 0.03
    s = sound(built.output)
    assert abs(loudness(s, 0.5) - 0.25) < 0.02            # 0.5 of the tone's 0.5
    assert any("tone.wav: 0.00 to 1.00 s" in n for n in built.notes)


def test_offset_start_and_a_fade_that_ends_with_the_shorter(tmp_path):
    """From 2.6 s into a 3 s file, starting 0.2 s in: the track ends at 0.6 s of film, and
    its fade out ends there, not at the picture's end; silence follows."""
    tone(tmp_path / "tone.wav", 3.0)
    built = build(two_shots(tmp_path, audio={"file": "tone.wav", "offset": 2.6, "start": 0.2,
                                             "fade": [0, 0.2]}))
    s = sound(built.output)
    assert abs(audio_length(built.output) - 1.0) < 0.03    # padded to the picture
    assert loudness(s, 0.1) < 1e-3                         # not started
    assert abs(loudness(s, 0.3, 0.02) - 0.5) < 0.02        # full before the fade
    assert loudness(s, 0.59, 0.005) < 0.1                  # nearly gone at its end
    assert loudness(s, 0.8) < 1e-3                         # silence after the track
    assert any("0.20 to 0.60 s" in n for n in built.notes)


def test_tracks_are_added_and_mute_leaves_them_out(tmp_path):
    tone(tmp_path / "a.wav", 2.0, 440)
    tone(tmp_path / "b.wav", 2.0, 660)
    tracks = [{"file": "a.wav", "volume": 0.4}, {"file": "b.wav", "volume": 0.4}]
    built = build(two_shots(tmp_path, audio=tracks))
    assert loudness(sound(built.output), 0.5) > 0.25      # more than either alone (0.2)
    muted = build(two_shots(tmp_path, audio=tracks), mute=True)
    assert ff.probe(muted.output, "stream=codec_type", stream=None).split() == ["video"]
    assert "audio: muted" in muted.notes


def test_a_track_that_cannot_play_is_an_error(tmp_path):
    tone(tmp_path / "tone.wav", 1.0)
    with pytest.raises(ValueError, match="offset 2 s is past the end"):
        build(two_shots(tmp_path, audio={"file": "tone.wav", "offset": 2}))
    with pytest.raises(ValueError, match="starts at 1.5 s, after the picture's 1 s"):
        build(two_shots(tmp_path, audio={"file": "tone.wav", "start": 1.5}))
    with pytest.raises(FileNotFoundError, match="no file"):
        build(two_shots(tmp_path, audio={"file": "missing.wav"}))


# -- preview -------------------------------------------------------------------------

def test_a_preview_copy_is_the_film_scaled_with_its_sound(tmp_path):
    tone(tmp_path / "tone.wav", 3.0)
    built = build(two_shots(tmp_path, audio={"file": "tone.wav"}), preview=46, crf=30)
    assert built.preview == tmp_path / "film_46p.mp4"
    assert ff.probe(built.preview, "stream=width,height").split() == ["82", "46"]
    assert ff.frame_count(built.preview) == 24
    assert abs(audio_length(built.preview) - 1.0) < 0.03
    film_frames, small = decode(built.output), decode(built.preview)
    assert abs(mean_colour(small[5]) - mean_colour(film_frames[5])).max() < 6
    assert built.table()[-2] == f"preview {built.preview}"


def test_a_preview_height_is_checked_before_building(tmp_path):
    path = two_shots(tmp_path)
    for height, message in [(45, "even number"), (180, "taller than the film's 90")]:
        with pytest.raises(ValueError, match=message):
            build(path, preview=height)
    with pytest.raises(ValueError, match="crf must be"):
        build(path, preview=46, crf=60)
    assert not (tmp_path / "clips").exists()


# -- one shot ------------------------------------------------------------------------

def test_only_builds_one_shots_finished_clip(tmp_path):
    path = two_shots(tmp_path)
    built = build(path, only="b")
    assert built.output == tmp_path / "film_b.mp4"
    assert [(s.name, s.planned, s.built) for s in built.shots] == [("b", 0.5, True)]
    assert ff.frame_count(built.output) == 12
    assert not (tmp_path / "film.mp4").exists()
    assert len(list((tmp_path / "clips").glob("shot_a_*.mp4"))) == 0
    assert not build(path).shots[1].built           # the whole film then keeps b's clip


def test_only_names_a_shot_of_the_film(tmp_path):
    with pytest.raises(KeyError, match="no shot 'c' \\(shots: a, b\\)"):
        build(two_shots(tmp_path), only="c")
    with pytest.raises(ValueError, match="whole film"):
        build(two_shots(tmp_path), only="a", preview=46)
