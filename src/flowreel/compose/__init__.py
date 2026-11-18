"""Compose: put frame folders and panels side by side in one picture (plan Section 9).

A layout file names the picture's size and its tiles, each a folder of frames
(``frame_00000.png`` ...) placed at a position and size. :func:`load` reads one; :func:`layout` composes its
frames into a folder of frames of its own.
"""
from flowreel.compose.layout_file import Label, Layout, Tile, from_dict, load
from flowreel.compose.tiling import ComposeReport, layout

__all__ = ["ComposeReport", "Label", "Layout", "Tile", "from_dict", "layout", "load"]
