"""Film: one ``film.yml`` of scenes turned into ``film.mp4`` (plan Section 10).

:mod:`flowreel.film.model` reads a film file into a :class:`~flowreel.film.model.Film`:
its scenes, each a layout of boxes, with style, audio and watermark.
:mod:`flowreel.film.boxes` draws one frame of a scene; :mod:`flowreel.film.scene_build`
plans the film, builds a clip per scene and joins them (:mod:`flowreel.film.build` holds
the join's parts), and writes its subtitles and contact sheet.
"""
