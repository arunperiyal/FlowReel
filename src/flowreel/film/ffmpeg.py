"""ffmpeg, found and checked once (plan Section 10.8).

FlowReel encodes clips and joins the film with ffmpeg, run as a program. pip cannot
install ffmpeg, so it comes from conda-forge into the same environment as FlowReel
(``environment.yml``)::

    conda install -n flexflow_env -c conda-forge ffmpeg

**Which ffmpeg.** The first of:

1. the file named by the ``FFMPEG`` environment variable;
2. ``ffmpeg`` beside the running Python (``<env>/bin/ffmpeg``), so the environment's own
   copy is used even when the environment is not activated;
3. ``ffmpeg`` on the path.

``ffprobe`` is taken from beside the ffmpeg found (or ``FFPROBE``). Other programs ship
copies of their own that can come first on the path; on the AFMS workstation that is
Tecplot's ffmpeg 4.3. The check below names the file it found, so such a copy is easy to
spot.

**The check**, once per process: the version is at least :data:`MIN_VERSION` (5.1
added ``-fps_mode``, which FlowReel uses to keep a clip's frame count exact), and the
build has the ``libx264`` encoder and the ``minterpolate``, ``xfade``, ``fade``,
``overlay`` and ``tpad`` filters. Anything missing is a :class:`FfmpegError` naming the
binary, what it lacks, and how to install a good one.
"""
from __future__ import annotations

import functools
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MIN_VERSION = (5, 1)
FILTERS = ("minterpolate", "xfade", "fade", "overlay", "tpad", "framerate", "scale")
ENCODERS = ("libx264",)
INSTALL = ("install one with: conda install -n flexflow_env -c conda-forge ffmpeg, "
           "or name one with the FFMPEG environment variable")


class FfmpegError(RuntimeError):
    """ffmpeg is missing, unsuitable, or failed."""


@dataclass(frozen=True)
class Ffmpeg:
    """A checked ffmpeg: the ``ffmpeg`` and ``ffprobe`` files, and the ``version`` as
    a tuple of numbers."""

    ffmpeg: Path
    ffprobe: Path
    version: tuple[int, ...]


def candidates() -> list[tuple[str, Path]]:
    """Where ffmpeg is looked for, in order: ``(how it was found, path)``."""
    out = []
    if os.environ.get("FFMPEG"):
        out.append(("FFMPEG", Path(os.environ["FFMPEG"])))
    beside = Path(sys.executable).parent / "ffmpeg"
    if beside.is_file():
        out.append(("the Python environment", beside))
    found = shutil.which("ffmpeg")
    if found:
        out.append(("the path", Path(found)))
    return out


def parse_version(text: str) -> tuple[int, ...] | None:
    """The version in ``ffmpeg -version``'s first line (``ffmpeg version 8.0.1 ...``,
    ``ffmpeg version n7.1-3-g...``), or ``None`` for a build without a number."""
    m = re.match(r"ffmpeg version \D*(\d+)\.(\d+)(?:\.(\d+))?", text)
    if not m:
        return None
    return tuple(int(g) for g in m.groups() if g is not None)


def _output(binary: Path, *args: str) -> str:
    try:
        done = subprocess.run([str(binary), "-hide_banner", *args], capture_output=True,
                              text=True, timeout=60)
    except OSError as error:
        raise FfmpegError(f"cannot run {binary}: {error}; {INSTALL}") from None
    return done.stdout + done.stderr


def check(binary: Path, how: str = "") -> Ffmpeg:
    """Check the ffmpeg at ``binary`` (see the module); ``how`` it was found goes in
    the error."""
    where = f"{binary}" + (f" (from {how})" if how else "")
    version = parse_version(_output(binary, "-version"))
    if version is None:
        raise FfmpegError(f"{where} did not report an ffmpeg version; {INSTALL}")
    if version[:2] < MIN_VERSION:
        raise FfmpegError(
            f"{where} is ffmpeg {'.'.join(map(str, version))}; FlowReel needs "
            f"{'.'.join(map(str, MIN_VERSION))} or later (another program's copy may come "
            f"first on the path); {INSTALL}")
    filters = set(re.findall(r"^\s*\S+\s+(\w+)\s", _output(binary, "-filters"), re.M))
    encoders = set(re.findall(r"^\s*V\S*\s+(\w+)\s", _output(binary, "-encoders"), re.M))
    missing = [f"filter {f}" for f in FILTERS if f not in filters] + \
              [f"encoder {e}" for e in ENCODERS if e not in encoders]
    if missing:
        raise FfmpegError(f"{where} lacks {', '.join(missing)}; {INSTALL}")
    probe = Path(os.environ["FFPROBE"]) if os.environ.get("FFPROBE") else \
        binary.with_name("ffprobe")
    if not probe.is_file():
        raise FfmpegError(f"no ffprobe beside {where} (set FFPROBE); {INSTALL}")
    return Ffmpeg(binary, probe, version)


@functools.lru_cache(maxsize=None)
def find() -> Ffmpeg:
    """The ffmpeg to use: the first candidate, checked (once per process)."""
    found = candidates()
    if not found:
        raise FfmpegError(f"ffmpeg not found (FFMPEG unset, none beside {sys.executable}, "
                          f"none on the path); {INSTALL}")
    how, path = found[0]
    return check(path, how)


def run(*args, quiet: bool = True) -> None:
    """Run ffmpeg with ``args`` (strings, numbers and paths). Raises
    :class:`FfmpegError` with the end of its message when it fails."""
    ff = find()
    command = [str(ff.ffmpeg), "-y", "-hide_banner", "-nostdin"]
    if quiet:
        command += ["-loglevel", "error"]
    command += [str(a) for a in args]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise FfmpegError(f"ffmpeg failed ({ff.ffmpeg}):\n{done.stderr[-3000:]}")


def probe(path, *entries: str, stream: str | None = "v:0", count: bool = False) -> str:
    """``ffprobe``'s values of ``entries`` (such as ``stream=nb_read_frames``) for
    ``path``, as text, one per line."""
    ff = find()
    command = [str(ff.ffprobe), "-v", "error"]
    if stream:
        command += ["-select_streams", stream]
    if count:
        command += ["-count_frames"]
    command += ["-show_entries", ",".join(entries), "-of", "default=nw=1:nk=1", str(path)]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        raise FfmpegError(f"ffprobe failed on {path}:\n{done.stderr[-2000:]}")
    return done.stdout.strip()


def length(path) -> float:
    """Seconds in a video or audio file, as measured, not as planned."""
    return float(probe(path, "format=duration", stream=None))


def frame_count(path) -> int:
    """The number of video frames in ``path``, counted by decoding."""
    return int(probe(path, "stream=nb_read_frames", count=True))
