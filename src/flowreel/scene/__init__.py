"""Shots: the shot file, layers, cameras and rendering (plan Section 7).

``render_frame(shot, frame)`` draws one frame; ``render(shot, ...)`` writes a shot's
frames to files (:mod:`flowreel.scene.rendering`).
"""
import importlib

__all__ = ["render", "render_frame"]


def __getattr__(name):
    # Imported on first use, so that reading a shot file does not load the renderer.
    if name in __all__:
        return getattr(importlib.import_module("flowreel.scene.rendering"), name)
    raise AttributeError(f"module 'flowreel.scene' has no attribute {name!r}")
