"""``film build --watch``: build the film again each time something it is made from
changes (plan Section 19.9, Phase 8 branch 7).

What the film is made from is not listed: the film file names cards, text files, frame
folders, layouts and sound, and those name more. Instead the watch looks at every file
under the film file's folder, by size and time of change, polled (no dependency on the
operating system's file events, which do not work over every network file system).
Left out: the build's own output (the clips folder, ``.flowreel/``, films and subtitles
at the top of the folder, the contact sheet) and folders reached through a link, such as
``data/``, which are the simulation's and can be large.

A change starts a build once the files have stopped changing for a moment, so a render
still writing frames is not built half way; a change made while a build runs starts
another when it ends. A build that fails says why and waits for the next change. The
build itself keeps every clip whose inputs did not change, so only what changed is made
again.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Callable

#: Folders under the film's folder that are FlowReel's output or tools', not inputs.
SKIP_DIRS = ("clips", ".flowreel", ".git", "__pycache__")
#: Files at the top of the film's folder that a build or a check writes.
SKIP_SUFFIXES = (".mp4", ".srt", ".part")
SKIP_FILES = ("contact.png",)


def fingerprint(root: str | Path, skip: tuple[Path, ...] = ()) -> tuple:
    """The size and time of change of every file under ``root`` that a film may be made
    from (see the module), as a sorted tuple; ``skip`` adds folders to leave out."""
    root = Path(root)
    skip_paths = {Path(s).resolve() for s in skip}
    out = []
    for folder, dirs, files in os.walk(root):          # links to folders are not followed
        here = Path(folder)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and (here / d).resolve() not in skip_paths)
        for name in files:
            if here == root and (name.endswith(SKIP_SUFFIXES) or name in SKIP_FILES):
                continue
            try:
                st = (here / name).stat()
            except OSError:                            # removed meanwhile
                continue
            out.append((str((here / name).relative_to(root)), st.st_size, st.st_mtime_ns))
    return tuple(sorted(out))


def watch(film: str | Path, build_once: Callable[[], None], *,
          say: Callable[[str], None] = print, interval: float = 1.0, settle: float = 0.5,
          skip: tuple[Path, ...] = (), stop: Callable[[], bool] | None = None) -> None:
    """Call ``build_once()`` now and after each change under the folder of ``film``
    (see the module), polling every ``interval`` seconds, until ``stop()`` is true or
    the process is interrupted. A change is built once nothing has changed for
    ``settle`` seconds. An error from ``build_once`` is said, and the watch goes on."""
    root = Path(film).resolve().parent
    seen = None
    while True:
        now = fingerprint(root, skip)
        if now != seen:
            time.sleep(settle)
            later = fingerprint(root, skip)
            if later != now:                           # still being written
                continue
            try:
                build_once()
            except Exception as exc:                   # an edit half done: say, and wait
                say(f"not built: {exc}")
            seen = later                               # a change made during it: build again
            say(f"watching {root} for changes (Ctrl-C to stop)")
        if stop is not None and stop():
            return
        time.sleep(interval)
