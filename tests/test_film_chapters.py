"""Chapters: in the film file, timed by the timeline, written into the film and its
preview at the join, and as YouTube timestamps."""
import pytest

from flowreel import film
from flowreel.film import ffmpeg as ff
from flowreel.film.build import build
from flowreel.film.chapters import metadata_text, timestamp, youtube_notes, youtube_text
from flowreel.film.schema import Chapter, from_dict
from flowreel.film.timeline import TimedChapter
from flowreel.scene.errors import ConfigError

from film_project import film_file, frames, need_ffmpeg


def project(tmp_path, chapters=("One", None, {"title": "Two = 2", "at": 0.25})):
    for name, start in (("a", 0), ("b", 10), ("c", 20)):
        frames(tmp_path / name, 12, start=start)
    shots = [{"name": n, "frames": n} for n in "abc"]
    shots[0]["freezes"] = [{"at": 0.25, "hold": 0.5}]
    for shot, ch in zip(shots, chapters):
        if ch is not None:
            shot["chapter"] = ch
    return film_file(tmp_path, shots)


def test_a_chapter_is_a_title_or_a_title_and_a_time():
    f = from_dict({"shots": [
        {"name": "a", "frames": "a", "chapter": " Opening "},
        {"name": "b", "frames": "b", "chapter": {"title": "Set-up", "at": 1.5}},
        {"name": "c", "frames": "c"}]})
    assert [s.chapter for s in f.shots] == [Chapter("Opening"), Chapter("Set-up", 1.5), None]


@pytest.mark.parametrize("chapter, message", [
    ({"at": 1}, "missing key 'title'"),
    ({"title": "x", "when": 1}, "when"),
    ("", "one line"),
    ({"title": "a\nb"}, "one line"),
    ({"title": "x", "at": -1}, "at"),
])
def test_bad_chapters_name_their_key(chapter, message):
    with pytest.raises(ConfigError, match=message) as error:
        from_dict({"shots": [{"name": "a", "frames": "a", "chapter": chapter}]}, "film.yml")
    assert "film.yml: shots[0].chapter" in str(error.value)


def test_chapters_take_their_times_from_the_timeline(tmp_path):
    line = film.timeline(film.load(project(tmp_path)))
    # a: 0.5 s of frames + a 0.5 s freeze; b and c: 0.5 s each
    assert line.chapters == [TimedChapter("One", "a", 0.0, 1.75),
                             TimedChapter("Two = 2", "c", 1.75, 2.0)]


def test_a_chapter_past_its_shot_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="starts at 0.5 s, at or after the end of shot 'c'"):
        film.timeline(film.load(project(tmp_path, ("One", None, {"title": "x", "at": 0.5}))))


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


def read_chapters(path):
    import json
    import subprocess
    done = subprocess.run([str(ff.find().ffprobe), "-v", "error", "-show_chapters", "-of",
                           "json", str(path)], capture_output=True, text=True, check=True)
    return [(c["tags"]["title"], round(float(c["start_time"]), 3), round(float(c["end_time"]), 3))
            for c in json.loads(done.stdout)["chapters"]]


def test_chapters_are_written_into_the_film_and_its_preview(tmp_path):
    need_ffmpeg()
    built = build(project(tmp_path), preview=46)
    expected = [("One", 0.0, 1.75), ("Two = 2", 1.75, 2.0)]
    assert read_chapters(built.output) == expected
    assert read_chapters(built.preview) == expected
    assert built.chapters == tmp_path / "chapters.txt"
    assert built.chapters.read_text() == "0:00 One\n0:01 Two = 2\n"
    assert "chapters: 2 of them; YouTube needs at least 3" in built.notes
    assert ff.frame_count(built.output) == 48


def test_chapters_and_sound_together(tmp_path):
    need_ffmpeg()
    ff.run("-f", "lavfi", "-i", "sine=duration=3", tmp_path / "tone.wav")
    path = project(tmp_path)
    text = path.read_text() + "audio: {file: tone.wav}\n"
    path.write_text(text)
    built = build(path)
    assert read_chapters(built.output)[0] == ("One", 0.0, 1.75)
    # the third stream is mp4's chapter track, which QuickTime reads
    assert ff.probe(built.output, "stream=codec_type", stream=None).split() == [
        "video", "audio", "data"]


def test_a_film_without_chapters_writes_none(tmp_path):
    need_ffmpeg()
    built = build(project(tmp_path, (None, None, None)))
    assert built.chapters is None and read_chapters(built.output) == []
    assert not (tmp_path / "chapters.txt").exists()
