"""Reading FlowReel's YAML files (plan Section 15).

:func:`read_yaml` parses a file and reports a syntax error with its line, as a
:class:`~flowreel.scene.errors.ConfigError` naming the file.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from flowreel.scene.errors import ConfigError


def parse(path: str | Path):
    """The parsed contents of the YAML file at ``path``."""
    path = Path(path)
    try:
        return yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"line {mark.line + 1}" if mark else "syntax"
        raise ConfigError(f"{where}: {getattr(exc, 'problem', None) or exc}", path) from None


def read_yaml(path: str | Path):
    """The contents of the YAML file at ``path``."""
    return parse(path)
