"""Film: one ``film.yml`` turned into ``film.mp4`` (plan Section 10).

:func:`load` reads a film file into a :class:`Film`: its shots in order (frames,
layouts, cards and holds), style, audio and watermark.
"""
from flowreel.film.schema import Film, Freeze, Rate, Shot, from_dict, load

__all__ = ["Film", "Freeze", "Rate", "Shot", "from_dict", "load"]
