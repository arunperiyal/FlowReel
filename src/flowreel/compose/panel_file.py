"""The panel file (plan Section 9.2): a matplotlib figure drawn once per frame.

.. code-block:: yaml

    type: series
    size: [640, 1080]
    times: {shot: shots/bare_wake.yml}     # or a list of times
    style: styles/film.yml
    ...                                     # the keys of the panel's type

``times`` are the physical times of the frames, in the source's time unit: the frame
times of a shot (the time of the step each frame shows), or a list. Frame ``i`` of the
panel is drawn at ``times[i]``, so a panel made from a shot's times lines up frame by
frame with that shot's frames in a layout.

:func:`load` reads a file, :func:`from_dict` a parsed mapping; the keys of the type are
kept in ``options`` and checked by the type. Both raise
:class:`~flowreel.scene.errors.ConfigError` naming the file and the key path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


from flowreel.compose.style import Style, parse_style
from flowreel.scene.errors import Checker, ConfigError

KEYS = ("type", "name", "size", "times", "style")
DEFAULT_SIZE = (640, 360)


@dataclass
class PanelFile:
    """A parsed panel file.

    ``type`` names the panel; ``name`` the output folder (default: the file's stem);
    ``size`` is ``(width, height)`` in pixels. ``times`` is a tuple of times, or the
    resolved path of a shot whose frame times are the panel's (:func:`frame_times`).
    ``options`` are the keys of the type, as written. ``file`` is the panel file, and
    relative paths in it are taken from its folder.
    """

    type: str
    name: str
    size: tuple[int, int]
    times: tuple[float, ...] | Path
    style: Style = field(default_factory=Style)
    options: dict = field(default_factory=dict)
    file: str | None = None

    @property
    def folder(self) -> Path:
        """Where relative paths in the panel file start."""
        return Path(self.file).parent if self.file else Path(".")


def load(path: str | Path) -> PanelFile:
    """Read the panel file at ``path``. Errors name the file."""
    from flowreel.yamlfile import read_yaml
    path = Path(path)
    data = read_yaml(path)
    return from_dict(data, file=str(path))


def from_dict(data, file: str | None = None) -> PanelFile:
    """Check the keys every panel has; keep the others in ``options``."""
    check = Checker(file)
    if not isinstance(data, dict):
        raise check.error("expected a mapping")
    for key in ("type", "times"):
        if key not in data:
            raise check.error(f"missing key {key!r}")
    folder = Path(file).parent if file else Path(".")
    kind = check.at("type").string(data["type"])
    name = check.at("name").string(data.get("name", Path(file).stem if file else kind))
    size = _size(data.get("size", DEFAULT_SIZE), check.at("size"))
    times = _times(data["times"], check.at("times"), folder)
    style = parse_style(data.get("style"), check.at("style"), folder)
    options = {k: v for k, v in data.items() if k not in KEYS}
    return PanelFile(kind, name, size, times, style, options, file)


def _size(value, check: Checker) -> tuple[int, int]:
    items = check.sequence(value)
    if len(items) != 2:
        raise check.error(f"expected [width, height], got {len(items)} entries")
    return tuple(check.at(i).integer(v, minimum=1) for i, v in enumerate(items))


def _times(value, check: Checker, folder: Path):
    """``times: [t0, t1, ...]`` (not decreasing) or ``times: {shot: FILE}``."""
    if isinstance(value, dict):
        spec = check.mapping(value, ("shot",), required=("shot",))
        path = (folder / check.at("shot").string(spec["shot"])).resolve()
        if not path.is_file():
            raise check.at("shot").error(f"no shot file {path}")
        return path
    items = check.sequence(value, minimum=1)
    times = tuple(check.at(i).number(t) for i, t in enumerate(items))
    for i, (a, b) in enumerate(zip(times, times[1:])):
        if b < a:
            raise check.at(i + 1).error(f"times must not decrease: {b:g} after {a:g}")
    return times


def frame_times(panel: PanelFile) -> list[float]:
    """The panel's times: its list, or the time of the step each frame of its shot
    shows (the shot's source is opened and its steps listed; no field is read)."""
    if not isinstance(panel.times, Path):
        return list(panel.times)
    from flowreel.project import project_for
    from flowreel.project.names import declare
    from flowreel.scene.plan import plan
    from flowreel.scene.rendering import open_source
    from flowreel.scene.shot import load as load_shot
    check = Checker(panel.file, ("times", "shot"))
    try:
        shot = load_shot(panel.times)
        source = declare(open_source(shot), project_for(shot.file))
        fp = plan(shot, source)
    except (ConfigError, OSError, ValueError, KeyError) as exc:
        raise check.error(f"cannot take the frame times of {panel.times}: {exc}") from None
    return [fp.times[fp.time.step(i)] for i in range(fp.n_frames)]
