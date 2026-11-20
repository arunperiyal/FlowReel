"""Phase 4's check, in this repository: the AFMS film written for FlowReel
(``tools/afms_film.py``, from the prototype's ``make_film.py`` and ``film_text.toml``)
has the prototype's lengths and captions.

Frames: generated folders of the film's own counts (tiny pictures; only their number
matters to the lengths). The prototype's own functions give what the film must be:

- each shot's planned length, ``make_film.duration``, equals FlowReel's timeline;
- each caption's start and end in its shot, ``make_film.shot_captions`` (freeze text
  included), equal FlowReel's;
- every caption drawn by ``make_film.caption_image`` matches FlowReel's drawing of the
  written text file, with the limits of Phase 2's golden tests; one moved by a few
  pixels must fail them;
- the opening card drawn by ``make_film.opening_card`` (its logo a generated one)
  matches FlowReel's drawing of ``cards/opening.yml``.

The rebuild from the real frames is run on the workstation (``docs/PLAN.md``, under
Phase 4's done line).
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel.film import load, timeline
from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import afms_film  # noqa: E402

#: Frames of each prototype frame folder, from film_text.toml's shot lengths: 12 s at
#: 24 fps, 15.1 s and 6.1 s at 8 fps (T1 to T2 and T1 to EXTRA_T2, one frame per 5
#: steps), 6 s at 24 fps.
COUNTS = {"bare_domain": 288, "bare_reveal": 121, "carve": 288, "helical_reveal": 121,
          "compare": 121, "bare_panel": 121, "helical_panel": 121, "top": 49, "slices": 49,
          "helical_section": 49, "wall": 49, "liftmap": 144}
#: The film's length: the card, the 24 fps shots, the 8 fps shots (film_text.toml's
#: header rounds 121 / 8 to 15.1 s and 49 / 8 to 6.1 s), the two freezes and the hold.
TOTAL = 7 + (288 + 288 + 144) / 24 + (3 * 121 + 4 * 49) / 8 + 2 * 6 + 13     # 131.875 s
GREY = (90, 110, 130, 255)
PAD = 20


def make_logo(path: Path) -> None:
    """A stand-in for the logo: a white ring on transparency (no logos here)."""
    from PIL import ImageDraw
    logo = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
    ImageDraw.Draw(logo).ellipse((20, 20, 280, 280), outline=(255, 255, 255, 255), width=30)
    path.parent.mkdir(parents=True, exist_ok=True)
    logo.save(path)


@pytest.fixture(scope="module")
def afms(tmp_path_factory):
    """The AFMS project written by the tool, its frame folders generated, the
    prototype pointed at them; ``(folder, make_film, text, film)``."""
    folder = tmp_path_factory.mktemp("afms")
    afms_film.write(folder)
    tiny = Image.new("RGB", (4, 4))
    for name, n in COUNTS.items():
        (folder / "frames" / name).mkdir(parents=True)
        for i in range(n):
            tiny.save(folder / "frames" / name / f"frame_{i:05d}.png")
    mf, text = afms_film.prototype()
    mf.FRAMES = folder / "frames"
    make_logo(folder / mf.LOGO.relative_to(mf.ROOT))
    from flowreel.compose.style import register_fonts
    register_fonts()
    return folder, mf, text, load(folder / "film.yml")


def test_the_tool_keeps_files_unless_forced(afms):
    folder = afms[0]
    with pytest.raises(FileExistsError, match="--force"):
        afms_film.write(folder)


def test_planned_lengths_equal_the_prototypes(afms):
    _, mf, text, film = afms
    line = timeline(film)
    assert [ts.shot.name for ts in line.shots] == [s["name"] for s in mf.SHOTS]
    for shot in mf.SHOTS:
        assert line.shot(shot["name"]).length == pytest.approx(mf.duration(shot, text),
                                                               abs=1e-9), shot["name"]
    assert line.length == pytest.approx(TOTAL, abs=1e-9)


def test_caption_times_equal_the_prototypes(afms):
    _, mf, text, film = afms
    line = timeline(film)
    for shot in mf.SHOTS:
        ts = line.shot(shot["name"])
        theirs = sorted((tuple(c["lines"]), round(c["start"] if "start" in c else 0, 6),
                         round(min(c["end"], ts.length), 6))
                        for c in mf.shot_captions(shot, text, mf.duration(shot, text)))
        ours = sorted((c.caption.lines, round(c.start - ts.start, 6), round(c.end - ts.start, 6))
                      for c in line.captions_on(shot["name"]))
        assert ours == theirs, shot["name"]


def seen(image):
    return np.asarray(Image.alpha_composite(Image.new("RGBA", image.size, GREY), image)
                      .convert("RGB"))


def compared(ours, gold):
    """The difference inside the golden caption's extent, padded."""
    ys, xs = np.nonzero(np.asarray(gold)[..., 3])
    top, bottom = max(0, ys.min() - PAD), ys.max() + PAD
    left, right = max(0, xs.min() - PAD), xs.max() + PAD
    return difference(seen(ours)[top:bottom, left:right], seen(gold)[top:bottom, left:right])


def pairs(afms):
    """Each caption of the film: the prototype's dict and FlowReel's caption."""
    _, mf, text, film = afms
    line = timeline(film)
    out = []
    for shot in mf.SHOTS:
        ours = {c.caption.lines: c.caption for c in line.captions_on(shot["name"])}
        for c in mf.shot_captions(shot, text, mf.duration(shot, text)):
            out.append((c, ours[tuple(c["lines"])]))
    return out


def test_every_caption_is_drawn_in_place(afms, tmp_path):
    from flowreel.film.draw import caption_image
    _, mf, _, film = afms
    found = pairs(afms)
    assert len(found) == 32
    bad = []
    for k, (theirs, ours) in enumerate(found):
        path = tmp_path / f"gold_{k}.png"
        mf.caption_image(theirs, path)
        gold = Image.open(path).convert("RGBA")
        image, _ = caption_image(ours, film.style, film.size)
        mean, clear = compared(image, gold)
        if not (mean < MEAN_LIMIT and clear < CLEAR_LIMIT):
            bad.append((theirs["lines"][0], mean, clear))
    assert not bad


def test_a_moved_caption_fails(afms, tmp_path):
    from flowreel.film.draw import caption_image
    _, mf, _, film = afms
    theirs, ours = next((t, o) for t, o in pairs(afms) if isinstance(t.get("place"), list)
                        and t["place"][0] != "centre")
    mf.caption_image(theirs, tmp_path / "gold.png")
    x, y = theirs["place"]
    image, _ = caption_image(replace(ours, place=(x + 4, y + 3)), film.style, film.size)
    mean, clear = compared(image, Image.open(tmp_path / "gold.png").convert("RGBA"))
    assert mean > MEAN_LIMIT and clear > CLEAR_LIMIT, (mean, clear)


def test_the_opening_card_matches(afms, tmp_path, monkeypatch):
    from flowreel.film.cards import card_image, load_card
    folder, mf, text, film = afms
    monkeypatch.setattr(mf, "LOGO", folder / mf.LOGO.relative_to(mf.ROOT))
    # FlowReel lays card text out with Pillow's basic engine on every machine; so must
    # the prototype here, or a Pillow built with raqm (airavata's) kerns its card.
    from PIL import ImageFont
    truetype = ImageFont.truetype
    monkeypatch.setattr(ImageFont, "truetype", lambda *a, **k: truetype(
        *a, **{"layout_engine": ImageFont.Layout.BASIC, **k}))
    mf.opening_card(tmp_path / "gold.png", text["opening"])
    gold = np.asarray(Image.open(tmp_path / "gold.png").convert("RGB"))
    ours = np.asarray(card_image(load_card(folder / "cards" / "opening.yml"), film.style))
    mean, clear = difference(ours, gold)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)
