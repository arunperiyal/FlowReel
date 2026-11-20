"""Film: one ``film.yml`` turned into ``film.mp4`` (plan Section 10).

:func:`load` reads a film file into a :class:`Film`: its shots in order (frames,
layouts, cards and holds), style, audio and watermark. :func:`timeline` lays it out:
each shot's start and length, its freezes, its captions' and chapters' times in film
seconds. :func:`flowreel.film.build.build` makes the film; :mod:`flowreel.film.check`
writes its subtitles and contact sheet.
"""
from flowreel.film.schema import Film, Freeze, Rate, Shot, from_dict, load
from flowreel.film.timeline import Timeline, timeline

__all__ = ["Film", "Freeze", "Rate", "Shot", "Timeline", "from_dict", "load", "timeline"]
