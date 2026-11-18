"""Compose: put frame folders and panels side by side in one picture (plan Section 9).

A layout file names the picture's size and its tiles, each a folder of frames
(``frame_00000.png`` ...) placed at a position and size. :func:`load` reads one.
"""
from flowreel.compose.layout import Label, Layout, Tile, from_dict, load

__all__ = ["Label", "Layout", "Tile", "from_dict", "load"]
