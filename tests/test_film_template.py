"""film template: a film file with every key at its default, that loads."""
import re

import yaml

from flowreel.film import schema
from flowreel.film.schema import from_dict
from flowreel.film.template import template


def keys(text: str) -> set[str]:
    return set(re.findall(r"([a-z_]+):", text))


def test_every_key_is_written():
    text = template()
    for group in (schema.KEYS, schema.SHOT_KEYS, schema.STYLE_KEYS, schema.COLOUR_KEYS,
                  schema.CAPTION_KEYS, schema.AUDIO_KEYS, schema.WATERMARK_KEYS,
                  schema.RATE_KEYS, schema.FREEZE_KEYS, schema.CHAPTER_KEYS):
        assert set(group) <= keys(text), set(group) - keys(text)


def test_it_loads_at_the_defaults(tmp_path):
    film = from_dict(yaml.safe_load(template("wake", fps=30)), file=str(tmp_path / "film.yml"))
    assert film.fps == 30 and film.size == schema.DEFAULT_SIZE
    assert film.style == schema.FilmStyle() and film.audio == () and film.watermark is None
    (shot,) = film.shots
    assert shot.name == "wake" and shot.source == tmp_path / "frames" / "wake"
    assert shot.rate == schema.Rate(30, "interpolate") and shot.fade == (0.0, 0.0)


def test_commented_audio_and_watermark_load(tmp_path):
    lines = template().splitlines()
    start = next(k for k, l in enumerate(lines) if l.startswith("# audio:"))
    end = next(k for k, l in enumerate(lines) if l.startswith("shots:"))
    opened = [l[2:] if k in range(start, end) and not l.startswith("#   #") else l
              for k, l in enumerate(lines)]
    (tmp_path / "assets").mkdir()
    film = from_dict(yaml.safe_load("\n".join(opened)), file=str(tmp_path / "film.yml"))
    assert film.audio[0].volume == 1.0 and film.audio[0].fade == (0.0, 0.0)
    assert film.watermark.text == "A. Periyal" and film.watermark.opacity == schema.Watermark.opacity
