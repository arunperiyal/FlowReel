"""The join of a film of scenes (plan Sections 10.6, 10.8, 10.9): sound, the preview copy,
one scene alone, chapters in the film and for YouTube, subtitles' plain text, and the
``film`` commands."""
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from cli_harness import Shell
from flowreel.film import ffmpeg as ff
from flowreel.film.build import PREVIEW_CRF
from flowreel.film.chapters import (TimedChapter, metadata_text, timestamp, youtube_notes,
                                    youtube_text)
from flowreel.film.check import plain, srt_time
from flowreel.film.scene_build import build

from film_project import decode, frames, mean_colour, need_ffmpeg, scene_film, shot_scenes


@pytest.fixture(autouse=True)
def _ffmpeg():
    need_ffmpeg()


def two_scenes(tmp_path, **top):
    frames(tmp_path / "a", 12)
    frames(tmp_path / "b", 6, start=20)
    scenes = shot_scenes("ab", b={"rate": {"fps": 12, "to_output": "repeat"}})
    return scene_film(tmp_path, scenes, **top)


def test_a_second_build_keeps_every_clip(tmp_path):
    path = two_scenes(tmp_path)
    build(path)
    again = build(path)
    assert not any(s.built for s in again.shots)
    lines = again.table()
    assert lines[0].split() == ["scene", "planned", "measured"]
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
    built = build(two_scenes(tmp_path, audio={"file": "tone.wav", "volume": 0.5}))
    assert abs(audio_length(built.output) - 1.0) < 0.03
    assert abs(ff.length(built.output) - 1.0) < 0.03
    assert abs(loudness(sound(built.output), 0.5) - 0.25) < 0.02    # 0.5 of the tone's 0.5
    assert any("tone.wav: 0.00 to 1.00 s" in n for n in built.notes)


def test_offset_start_and_a_fade_that_ends_with_the_shorter(tmp_path):
    """From 2.6 s into a 3 s file, starting 0.2 s in: the track ends at 0.6 s of film, and
    its fade out ends there, not at the picture's end; silence follows."""
    tone(tmp_path / "tone.wav", 3.0)
    built = build(two_scenes(tmp_path, audio={"file": "tone.wav", "offset": 2.6, "start": 0.2,
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
    built = build(two_scenes(tmp_path, audio=tracks))
    assert loudness(sound(built.output), 0.5) > 0.25      # more than either alone (0.2)
    muted = build(two_scenes(tmp_path, audio=tracks), mute=True)
    assert ff.probe(muted.output, "stream=codec_type", stream=None).split() == ["video"]
    assert "audio: muted" in muted.notes


def test_a_track_that_cannot_play_is_an_error(tmp_path):
    tone(tmp_path / "tone.wav", 1.0)
    with pytest.raises(ValueError, match="offset 2 s is past the end"):
        build(two_scenes(tmp_path, audio={"file": "tone.wav", "offset": 2}))
    with pytest.raises(ValueError, match="starts at 1.5 s, after the picture's 1 s"):
        build(two_scenes(tmp_path, audio={"file": "tone.wav", "start": 1.5}))
    with pytest.raises(Exception, match="tone|no file|missing"):
        build(two_scenes(tmp_path, audio={"file": "missing.wav"}))


# -- preview -------------------------------------------------------------------------

def test_a_preview_copy_is_the_film_scaled_with_its_sound(tmp_path):
    tone(tmp_path / "tone.wav", 3.0)
    built = build(two_scenes(tmp_path, audio={"file": "tone.wav"}), preview=46, crf=30)
    assert built.preview == tmp_path / "film_46p.mp4"
    assert ff.probe(built.preview, "stream=width,height").split() == ["82", "46"]
    assert ff.frame_count(built.preview) == 24
    assert abs(audio_length(built.preview) - 1.0) < 0.03
    film_frames, small = decode(built.output), decode(built.preview)
    assert abs(mean_colour(small[5]) - mean_colour(film_frames[5])).max() < 6
    assert built.table()[-2] == f"preview {built.preview}"
    assert PREVIEW_CRF == 28


def test_a_preview_height_is_checked_before_building(tmp_path):
    path = two_scenes(tmp_path)
    for height, message in [(45, "even number"), (180, "taller than the film's 90")]:
        with pytest.raises(ValueError, match=message):
            build(path, preview=height)
    with pytest.raises(ValueError, match="crf must be"):
        build(path, preview=46, crf=60)
    assert not (tmp_path / "clips").exists()


# -- one scene -----------------------------------------------------------------------

def test_only_builds_one_scenes_finished_clip(tmp_path):
    path = two_scenes(tmp_path)
    built = build(path, only="b")
    assert built.output == tmp_path / "film_b.mp4"
    assert [(s.name, s.planned, s.built) for s in built.shots] == [("b", 0.5, True)]
    assert ff.frame_count(built.output) == 12
    assert not (tmp_path / "film.mp4").exists()
    assert not build(path).shots[1].built           # the whole film then keeps b's clip


def test_only_names_a_scene_of_the_film(tmp_path):
    with pytest.raises(KeyError, match="no scene 'c'"):
        build(two_scenes(tmp_path), only="c")
    with pytest.raises(ValueError, match="whole film"):
        build(two_scenes(tmp_path), only="a", preview=46)


# -- chapters ------------------------------------------------------------------------

def chapter_film(tmp_path, chapters=("One", None, {"title": "Two = 2", "at": 0.25})):
    for name, start in (("a", 0), ("b", 10), ("c", 20)):
        frames(tmp_path / name, 12, start=start)
    scenes = shot_scenes("abc")
    scenes[0]["layout"]["boxes"][0]["shot"]["freezes"] = [{"at": 0.25, "hold": 0.5}]
    for scene, ch in zip(scenes, chapters):
        if ch is not None:
            scene["chapter"] = ch
    return scene_film(tmp_path, scenes)


def read_chapters(path):
    done = subprocess.run([str(ff.find().ffprobe), "-v", "error", "-show_chapters", "-of",
                           "json", str(path)], capture_output=True, text=True, check=True)
    return [(c["tags"]["title"], round(float(c["start_time"]), 3), round(float(c["end_time"]), 3))
            for c in json.loads(done.stdout)["chapters"]]


def test_metadata_and_youtube_text():
    chapters = [TimedChapter("Opening", "a", 0.0, 7.0),
                TimedChapter("Set-up; a=b #1", "b", 7.0, 3725.25)]
    assert metadata_text(chapters, 3725.5) == (
        ";FFMETADATA1\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=7000\ntitle=Opening\n"
        "[CHAPTER]\nTIMEBASE=1/1000\nSTART=7000\nEND=3725500\ntitle=Set-up\\; a\\=b \\#1\n")
    assert youtube_text(chapters) == "0:00 Opening\n0:07 Set-up; a=b #1\n"
    assert [timestamp(t) for t in (0, 6.9999999, 59.5, 754, 3723.9)] == [
        "0:00", "0:07", "0:59", "12:34", "1:02:03"]


def test_youtube_notes_say_what_it_would_refuse():
    good = [TimedChapter(t, "s", a, b) for t, a, b in
            (("A", 0, 10), ("B", 10, 25), ("C", 25, 40))]
    assert youtube_notes(good) == []
    assert youtube_notes([]) == []
    late = [TimedChapter("A", "s", 2, 12), TimedChapter("B", "s", 12, 14)]
    assert youtube_notes(late) == [
        "chapters: the first starts at 0:02; YouTube needs one at 0:00",
        "chapters: 2 of them; YouTube needs at least 3",
        "chapters shorter than YouTube's 10 s: B"]


def test_chapters_are_written_into_the_film_and_its_preview(tmp_path):
    built = build(chapter_film(tmp_path), preview=46)
    expected = [("One", 0.0, 1.75), ("Two = 2", 1.75, 2.0)]
    assert read_chapters(built.output) == expected
    assert read_chapters(built.preview) == expected
    assert built.chapters == tmp_path / "chapters.txt"
    assert built.chapters.read_text() == "0:00 One\n0:01 Two = 2\n"
    assert "chapters: 2 of them; YouTube needs at least 3" in built.notes
    assert ff.frame_count(built.output) == 48


def test_chapters_and_sound_together(tmp_path):
    ff.run("-f", "lavfi", "-i", "sine=duration=3", tmp_path / "tone.wav")
    path = chapter_film(tmp_path)
    path.write_text(path.read_text() + "audio: {file: tone.wav}\n")
    built = build(path)
    assert read_chapters(built.output)[0] == ("One", 0.0, 1.75)
    # the third stream is mp4's chapter track, which QuickTime reads
    assert ff.probe(built.output, "stream=codec_type", stream=None).split() == [
        "video", "audio", "data"]


def test_a_film_without_chapters_writes_none(tmp_path):
    built = build(chapter_film(tmp_path, (None, None, None)))
    assert built.chapters is None and read_chapters(built.output) == []
    assert not (tmp_path / "chapters.txt").exists()


# -- subtitles' plain text -----------------------------------------------------------

def test_maths_is_written_as_plain_text():
    assert plain("uniform flow, $U = 1$") == "uniform flow, U = 1"
    assert plain(r"$12D \times 30D$") == "12D × 30D"
    assert plain(r"$\Delta p$, $\alpha$ and $\mathrm{Re}\,= 1000$") == "Δ p, α and Re = 1000"
    assert plain(r"costs \$5") == "costs $5"


def test_srt_times():
    assert srt_time(0) == "00:00:00,000"
    assert srt_time(3723.4567) == "01:02:03,457"


# -- the film commands ---------------------------------------------------------------

def words(out: str) -> dict[str, list[str]]:
    """Each printed line's words after its first, by its first."""
    return {w[0]: w[1:] for w in (line.split() for line in out.splitlines()) if w}


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    need_ffmpeg()
    folder = tmp_path_factory.mktemp("cli_film")
    frames(folder / "a", 12)
    frames(folder / "b", 12, start=20)
    a, b = shot_scenes("ab", b={"rate": {"fps": 12, "to_output": "repeat"}})
    a["layout"]["boxes"][0]["shot"]["freezes"] = [{"at": 0.25, "hold": 0.5}]
    a["layout"]["boxes"].append({"text": {"lines": ["Inlet, $U = 1$"]}, "place": "bottom",
                                 "at": [0.1, 0.4]})
    a["chapter"], b["chapter"] = "Start", "Middle"
    end = {"name": "end", "seconds": 1.0, "chapter": "End",
           "layout": {"boxes": [{"text": "The end", "place": "centre"}]}}
    scene_film(folder, [a, b, end])
    (folder / "flowreel.yml").write_text("")
    return folder


@pytest.fixture
def sh(project, tmp_path, monkeypatch):
    monkeypatch.chdir(project)
    return Shell(tmp_path / "store")


def test_build_then_keep(sh, project):
    status, out, err = sh.run("film build --preview 46")
    assert status == 0, err
    rows = words(out)
    assert rows["a"] == ["1.00", "s", "1.00", "s", "built"]
    assert rows["film"][0] == "3.00" and rows["preview"][0].endswith("film_46p.mp4")
    assert (project / "film.mp4").is_file() and (project / "film_46p.mp4").is_file()
    status, out, _ = sh.run("film build film.yml --mute")
    assert status == 0 and "built" not in out.replace("built in", "")


def test_build_only(sh, project):
    status, out, err = sh.run("film build --only b")
    assert status == 0, err
    assert words(out)["b"][:3] == ["1.00", "s", "1.00"] and (project / "film_b.mp4").is_file()


def test_build_errors(sh):
    status, _, err = sh.run("film build --crf 20")
    assert status != 0 and "--preview" in err
    status, _, err = sh.run("film build --preview 45")
    assert status != 0 and "even" in err
    status, _, err = sh.run("film build --only nobody")
    assert status != 0 and "no scene 'nobody'" in err
    status, _, err = sh.run("film build --only a --preview 46")
    assert status != 0 and "whole film" in err
    status, _, err = sh.run("film build missing.yml")
    assert status != 0 and "missing.yml" in err
    status, _, _ = sh.run("film")
    assert status != 0


def test_a_film_of_shots_is_not_read_any_more(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "flowreel.yml").write_text("")
    (tmp_path / "film.yml").write_text("shots: [{name: a, frames: a}]\n")
    status, _, err = Shell(tmp_path / "store").run("film lengths")
    assert status != 0 and "film of shots is not read any more" in err


def test_check(sh, project):
    status, out, err = sh.run("film check --at every:1 --width 80 --columns 2 -o sheet.png")
    assert status == 0, err
    sheet = Image.open(project / "sheet.png")
    assert sheet.width < 2 * 80 + 20 and "sheet.png" in out
    status, _, err = sh.run("film check --at sometimes")
    assert status != 0 and "every:S" in err


def test_lengths_measured_from_the_last_build(sh, project, tmp_path):
    status, out, err = sh.run("film lengths --clips " + str(tmp_path / "none"))
    assert status == 0, err
    rows = words(out)
    assert rows["b"] == ["1.00", "s", "-"] and rows["film"] == ["3.00", "s", "-"]
    assert "no finished clip" in out
    sh.run("film build")
    rows = words(sh.run("film lengths")[1])
    assert rows["b"] == ["1.00", "s", "1.00", "s"]
    assert rows["Middle"] == ["0:01", "1.00", "s", "1.00", "s"]
    assert rows["End"] == ["0:02", "2.00", "s", "1.00", "s"]


def test_srt_and_chapters(sh, project):
    status, out, err = sh.run("film srt -o subs.srt")
    assert status == 0, err
    assert "1 subtitles" in out and (project / "subs.srt").read_text().startswith("1\n00:00:00,100")
    status, out, err = sh.run("film chapters")
    assert status == 0
    assert out == "0:00 Start\n0:01 Middle\n0:02 End\n" and "YouTube's 10 s" in err
    status, out, _ = sh.run("film chapters -o ch.txt")
    assert (project / "ch.txt").read_text() == "0:00 Start\n0:01 Middle\n0:02 End\n"


def test_template(sh, tmp_path):
    status, out, _ = sh.run("film template")
    assert status == 0 and "scenes:" in out and "shots/my_shot.yml" in out
    target = tmp_path / "t.yml"
    assert sh.run(f"film template wake --fps 30 -o {target}")[0] == 0
    assert "fps: 30" in target.read_text()
    status, _, err = sh.run(f"film template -o {target}")
    assert status != 0 and "--force" in err
    assert sh.run(f"film template -o {target} --force")[0] == 0
    status, out, _ = sh.run("film template --layout")
    assert status == 0 and "boxes:" in out


def test_project_context_finds_film_yml(project, tmp_path, monkeypatch):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    sh = Shell(tmp_path / "store")
    status, _, err = sh.run("film lengths")
    assert status != 0 and "film.yml" in err
    assert sh.run(f"use project:{project}")[0] == 0
    status, out, err = sh.run("film lengths")
    assert status == 0, err
    assert words(out)["b"][:2] == ["1.00", "s"] and str(project / "film.yml") in out + err
    status, _, err = sh.run(f"use project:{elsewhere}")
    assert status != 0 and "not a project" in err
