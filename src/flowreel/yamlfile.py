"""Reading FlowReel's YAML files, with ``include:`` (plan Section 15).

Every file may include others, so styles and text can be shared between films:

.. code-block:: yaml

    include: styles/film.yml          # a mapping: its keys, under this file's own
    size: [1280, 720]                  # this file's keys win

    # in a list, an entry that is only an include is replaced by the included list
    - include: text/common.yml
    - {lines: ['One more caption'], at: [2, 5]}

In a mapping, ``include`` is a file or a list of files; each must hold a mapping, and
they are merged in order beneath the mapping's own keys (mappings inside are merged
the same way, key by key; anything else is replaced). In a list, an entry
``{include: FILE}`` is replaced by the entries of that file, which must hold a list.
Includes may include others; a file that includes itself is an error. Paths are taken
from the including file's folder.

:func:`read_yaml` reads a file with its includes; a syntax error is reported with its
line, as a :class:`~flowreel.scene.errors.ConfigError` naming the file.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from flowreel.scene.errors import Checker, ConfigError

INCLUDE = "include"


def parse(path: str | Path):
    """The parsed contents of the YAML file at ``path``, includes left as written."""
    path = Path(path)
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark else "syntax"
        raise ConfigError(f"{where}: {getattr(exc, 'problem', None) or exc}", path) from None
    except FileNotFoundError:
        raise ConfigError("no such file", path) from None


def read_yaml(path: str | Path, _seen: tuple = ()):
    """The contents of the YAML file at ``path``, with every ``include`` resolved."""
    path = Path(path).resolve()
    return _resolve(parse(path), Checker(path), path.parent, _seen + (path,))


def _resolve(value, check: Checker, folder: Path, seen: tuple):
    if isinstance(value, dict):
        own = {k: _resolve(v, check.at(k), folder, seen) for k, v in value.items() if k != INCLUDE}
        if INCLUDE not in value:
            return own
        base: dict = {}
        for path, at in _files(value[INCLUDE], check.at(INCLUDE), folder, seen):
            data = read_yaml(path, seen)
            if not isinstance(data, dict):
                raise at.error(f"{path} holds a {type(data).__name__}; a mapping can include "
                               "only a mapping")
            base = merged(base, data)
        return merged(base, own)
    if isinstance(value, list):
        out = []
        for i, item in enumerate(value):
            if isinstance(item, dict) and set(item) == {INCLUDE}:
                for path, at in _files(item[INCLUDE], check.at(i, INCLUDE), folder, seen):
                    data = read_yaml(path, seen)
                    if not isinstance(data, list):
                        raise at.error(f"{path} holds a {type(data).__name__}; an entry of a "
                                       "list can include only a list")
                    out += data
            else:
                out.append(_resolve(item, check.at(i), folder, seen))
        return out
    return value


def _files(value, check: Checker, folder: Path, seen: tuple):
    """The included files of an ``include`` value, resolved, with their checkers."""
    items = [value] if isinstance(value, str) else check.sequence(value, minimum=1)
    out = []
    for k, item in enumerate(items):
        at = check if isinstance(value, str) else check.at(k)
        path = (folder / at.string(item)).resolve()
        if path in seen:
            raise at.error(f"{path} includes itself")
        if not path.is_file():
            raise at.error(f"no file {path} to include")
        out.append((path, at))
    return out


def merged(base: dict, over: dict) -> dict:
    """``over`` on top of ``base``: mappings in both merged key by key, anything else
    taken from ``over``."""
    out = dict(base)
    for k, v in over.items():
        out[k] = merged(out[k], v) if isinstance(out.get(k), dict) and isinstance(v, dict) else v
    return out
