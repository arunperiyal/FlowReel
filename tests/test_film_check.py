"""Subtitles from the captions, and the contact sheet of stills with text in place."""
import numpy as np
import pytest
from PIL import Image

from flowreel import film
from flowreel.film.build import build
from flowreel.film.check import contact, contact_times, plain, srt_text, srt_time

from film_project import film_file, frames, need_ffmpeg

CAP = {"place": "centre", "size": 30, "colour": "#ff0000", "shadow": False, "fade": 0.1}


def project(tmp_path):
    frames(tmp_path / "a", 12)
    frames(tmp_path / "b", 12, start=20)
    return film_file(tmp_path, [
        {"name": "a", "frames": "a", "freezes": [{"at": 0.25, "hold": 0.5}],
         "text": [{**CAP, "lines": ["Inlet, $U = 1$", "second"], "at": [0.1, {"shot": "b", "at": 0.2}]}]},
        {"name": "b", "frames": "b", "text": [{**CAP, "lines": ["$12D \\times 30D$"], "at": [0.25, 0.45]}]}])


def test_maths_is_written_as_plain_text():
    assert plain("uniform flow, $U = 1$") == "uniform flow, U = 1"
    assert plain(r"$12D \times 30D$") == "12D × 30D"
    assert plain(r"$\Delta p$, $\alpha$ and $\mathrm{Re}\,= 1000$") == "Δ p, α and Re = 1000"
    assert plain(r"costs \$5") == "costs $5"


def test_srt_times():
    assert srt_time(0) == "00:00:00,000"
    assert srt_time(3723.4567) == "01:02:03,457"


def test_subtitles_carry_film_times_across_freezes_and_cuts(tmp_path):
    line = film.timeline(film.load(project(tmp_path)))
    assert srt_text(line) == (
        "1\n00:00:00,100 --> 00:00:01,200\nInlet, U = 1\nsecond\n\n"
        "2\n00:00:01,250 --> 00:00:01,450\n12D × 30D\n")


def test_stills_at_captions_freezes_or_every_few_seconds(tmp_path):
    line = film.timeline(film.load(project(tmp_path)))
    assert [(s.time, s.shot, s.why) for s in contact_times(line)] == [
        (0.65, "a", "Inlet, U = 1"), (1.35, "b", "12D × 30D")]
    assert [(s.time, s.shot, s.why) for s in contact_times(line, "freeze")] == [
        (0.5, "a", "freeze")]
    assert [(s.time, s.shot) for s in contact_times(line, "every:0.5")] == [
        (0.0, "a"), (0.5, "a"), (1.0, "b")]
    for bad in ("every:0", "every:x", "middle"):
        with pytest.raises(ValueError, match="contact"):
            contact_times(line, bad)


def test_a_whole_build_writes_the_subtitles(tmp_path):
    need_ffmpeg()
    built = build(project(tmp_path))
    assert built.srt == tmp_path / "film.srt"
    assert built.srt.read_text(encoding="utf-8").startswith("1\n00:00:00,100 --> ")
    assert f"srt {built.srt}" in built.table()


def test_the_contact_sheet_shows_each_caption_in_place(tmp_path):
    need_ffmpeg()
    path = contact(project(tmp_path), columns=4, width=160)
    assert path == tmp_path / "contact.png"
    sheet = Image.open(path).convert("RGB")
    gap, h = 4, 90
    assert sheet.width == gap + 2 * (160 + gap)          # two stills, as many columns
    for k in range(2):
        still = sheet.crop((gap + k * 164, gap, gap + k * 164 + 160, gap + h))
        f = np.asarray(still).astype(int)
        reds = ((f[..., 0] > 180) & (f[..., 1] < 90) & (f[..., 2] < 90)).sum()
        assert reds > 30                                  # the red caption, drawn in place
    with pytest.raises(ValueError, match="no freezes"):
        frames(tmp_path / "c", 4)
        contact(film_file(tmp_path / "c", [{"name": "c", "frames": "."}]), at="freeze")
