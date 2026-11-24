"""Compose: panels drawn per frame by matplotlib (plan Section 9.2).

A panel file describes a matplotlib figure drawn at each frame's time; :func:`panel` draws
its frames (``panel draw``). In a film of scenes a panel box is drawn by the build instead
(:class:`flowreel.film.boxes.PanelDrawer`), at the box's size.
"""
from flowreel.compose.panels import PanelReport, panel

__all__ = ["PanelReport", "panel"]
