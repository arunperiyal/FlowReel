"""Content keys for cached things (plan Section 11).

A key is a hash of everything that changes the thing: for a frame, the shot's settings
that reach the picture, every layer's values at that frame, the view, the step, the
picture size and the code. Keys, not file names or dates, decide whether a frame is
stale, which prevents the prototype's bug of stale clips kept because their names
matched.

"Code" is a hash of FlowReel's own source files, so a change to a layer re-renders
the frames it drew. It is coarse on purpose: a stale frame costs a wrong film, a
needless re-render only time.
"""
from __future__ import annotations

import dataclasses
import functools
import hashlib
import json
import os
from pathlib import Path

import numpy as np

import flowreel

KEY_FILE = ".keys.json"


@functools.lru_cache(maxsize=None)
def code_version(part: str = "") -> str:
    """Hash of the version and the ``.py`` files under ``flowreel/<part>`` (all when
    ``part`` is empty), read once per process."""
    root = Path(flowreel.__file__).parent
    h = hashlib.sha256(flowreel.__version__.encode())
    for path in sorted((root / part).rglob("*.py")):
        h.update(str(path.relative_to(root)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"cannot put {type(value).__name__} in a key")


def digest(parts: dict) -> str:
    """The key of ``parts``: a hash of their canonical JSON (sorted keys; numpy values,
    tuples and dataclasses as lists and mappings)."""
    text = json.dumps(parts, sort_keys=True, default=_plain, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def source_id(shot, source=None) -> list:
    """The shot's source in a key (see :func:`flowreel.scene.rendering.source_id`)."""
    from flowreel.scene.rendering import source_id as _id
    return _id(shot, source)


def file_stamps(source, step: int) -> list | None:
    """``[path, size, modification time]`` of each file ``source`` reads for ``step``
    (``Source.files``), so a file rewritten in place changes the key; ``None`` for a
    source that does not say. A ``{node}`` series pattern is stamped file by file."""
    files = getattr(source, "files", None)
    if files is None:
        return None
    out = []
    for path in files(step):
        path = Path(path)
        matches = ([path] if "{" not in path.name else
                   sorted(path.parent.glob(path.name.split("{")[0] + "*")))
        for p in matches:
            try:
                st = p.stat()
                out.append([str(p), st.st_size, st.st_mtime_ns])
            except OSError:
                out.append([str(p), None, None])
    return out


def frame_parts(scene, index: int) -> dict:
    """What decides the picture of frame ``index`` of ``scene`` (a
    :class:`~flowreel.scene.rendering.Scene`)."""
    from flowreel.project.names import bodies_key
    shot = scene.shot
    data = scene.data(index)
    crop = scene.crop(index)
    return {
        "code": code_version(),
        "source": source_id(shot, scene.source),
        "bodies": bodies_key(scene.source),
        "step": scene.plan.time.step(index),
        "files": file_stamps(scene.source, scene.plan.time.step(index)),
        "crop": None if crop is None else [list(crop.lo), list(crop.hi)],
        "size": list(scene.size),
        "background": shot.background,
        "antialias": shot.antialias,
        "stretch": shot.stretch,
        "lights": None if shot.lights is None else [dataclasses.asdict(lt) for lt in shot.lights],
        "view": scene.camera.key(index, data),
        "layers": [{"type": layer.name, **layer.key_fields(index)}
                   for layer in shot.layers],
    }


def frame_key(scene, index: int) -> str:
    """The key of frame ``index``; equal keys mean equal pictures."""
    parts = frame_parts(scene, index)
    watermark = getattr(scene.shot, "watermark", None)
    if watermark is not None:          # left out when absent, so older keys still hold
        from flowreel.film.watermark import key_fields
        parts["watermark"] = key_fields(watermark)
    reference = getattr(scene, "reference", None)
    if reference:                      # the project's reference values, likewise
        parts["reference"] = dict(sorted(reference.items()))
    return digest(parts)


class KeyStore:
    """The keys of the frames in a folder, in ``<folder>/.keys.json``.

    ``get(name)`` and ``put(name, key)``; :meth:`put` writes the file at once (through a
    temporary file), so an interrupted render keeps the keys of what it finished.
    """

    def __init__(self, folder: str | Path):
        self.path = Path(folder) / KEY_FILE
        try:
            self._keys = json.loads(self.path.read_text())
        except (FileNotFoundError, ValueError):
            self._keys = {}

    def get(self, name: str) -> str | None:
        """The stored key of frame file ``name``, or ``None``."""
        return self._keys.get(name)

    def put(self, name: str, key: str) -> None:
        """Store ``key`` for frame file ``name`` and save."""
        self._keys[name] = key
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._keys, indent=0, sort_keys=True))
        os.replace(tmp, self.path)

    def fresh(self, path: Path, key: str) -> bool:
        """True when ``path`` exists and was drawn with ``key``."""
        return path.exists() and self.get(path.name) == key
