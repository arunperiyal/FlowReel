"""The style shared by every panel (plan Section 9.2): fonts, colours and line widths.

A panel file's ``style`` is a mapping, the path of a YAML file holding one (so every
panel of a film can name the same file), or a mapping with ``from: FILE`` and keys that
change some of that file's values. The defaults are the AFMS film's plots: Lato for
text, DejaVu Sans for maths, light grey text on black.

.. code-block:: yaml

    style:
      from: styles/film.yml
      font_size: 20
"""
from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path


from flowreel.scene.errors import Checker

MATHS = ("dejavusans", "dejavuserif", "cm", "stix", "stixsans")


@dataclass(frozen=True)
class Style:
    """How panels look.

    ``font`` is the text's font family (the bundled Lato by default), ``font_size`` in
    points at 100 dots per inch (so a point is 100/72 pixels); ``maths`` is matplotlib's
    maths font set, for text between ``$``. ``background`` fills the panel; ``text``
    colours labels and ticks; ``grid`` colours the grid lines and the axes' edges.
    ``line_width`` and ``grid_width`` are in points, ``dot_size`` is the current-time
    dot's diameter in points. ``colours`` are given in turn to entries that name none.
    ``pad`` is the share of a data range added above and below it when a range is
    found from the data.
    """

    font: str = "Lato"
    font_size: float = 17.0
    maths: str = "dejavusans"
    background: str = "black"
    text: str = "#b4bec8"
    grid: str = "#3a4046"
    line_width: float = 2.2
    grid_width: float = 0.8
    dot_size: float = 8.0
    colours: tuple[str, ...] = ("#e8b04a", "#6ac1c8", "#d8707a", "#9bc96a", "#b49ae0")
    pad: float = 0.12

    @contextlib.contextmanager
    def applied(self):
        """matplotlib's settings for this style while the block runs."""
        import matplotlib as mpl
        register_fonts()
        with mpl.rc_context({
                "font.family": [self.font, "DejaVu Sans"], "font.size": self.font_size,
                "mathtext.fontset": self.maths, "axes.edgecolor": self.grid,
                "axes.labelcolor": self.text, "xtick.color": self.text,
                "ytick.color": self.text, "text.color": self.text,
                "figure.facecolor": self.background, "axes.facecolor": self.background,
                "savefig.facecolor": self.background}):
            yield


_REGISTERED = False


def register_fonts() -> None:
    """Make the bundled Lato known to matplotlib (once per process)."""
    global _REGISTERED
    if _REGISTERED:
        return
    from matplotlib import font_manager

    from flowreel.scene.text import FONTS
    for path in sorted(FONTS.glob("Lato-*.ttf")):
        font_manager.fontManager.addfont(str(path))
    _REGISTERED = True


KEYS = tuple(f.name for f in fields(Style))


def parse_style(value, check: Checker, folder: Path, _seen: tuple = ()) -> Style:
    """The :class:`Style` of a panel file's ``style`` (``None`` for the defaults): a
    mapping, a YAML file's path (from ``folder``), or a mapping with ``from: FILE``."""
    if value is None:
        return Style()
    if isinstance(value, str):
        value = {"from": value}
    spec = check.mapping(value, KEYS + ("from",))
    base = Style()
    if "from" in spec:
        path = (folder / check.at("from").string(spec["from"])).resolve()
        if path in _seen:
            raise check.at("from").error(f"{path} includes itself")
        if not path.is_file():
            raise check.at("from").error(f"no style file {path}")
        from flowreel.yamlfile import read_yaml
        data = read_yaml(path)
        base = parse_style(data or {}, Checker(path), path.parent, _seen + (path,))
    out = {}
    for key, v in spec.items():
        if key == "from":
            continue
        at = check.at(key)
        if key in ("font",):
            out[key] = at.string(v)
        elif key == "maths":
            out[key] = at.choice(v, MATHS)
        elif key in ("background", "text", "grid"):
            out[key] = colour(v, at)
        elif key == "colours":
            items = at.sequence(v, minimum=1)
            out[key] = tuple(colour(c, at.at(i)) for i, c in enumerate(items))
        else:
            n = at.number(v)
            if n < 0 or (n == 0 and key != "pad"):
                raise at.error(f"must be positive, got {n:g}")
            out[key] = n
    return replace(base, **out)


def colour(value, check: Checker) -> str:
    """A colour matplotlib reads: a name or ``#rrggbb``."""
    from matplotlib.colors import is_color_like
    if not isinstance(value, str) or not is_color_like(value):
        raise check.error(f"expected a colour name or '#rrggbb', got {value!r}")
    return value


def style_key(style: Style) -> dict:
    """The style as a key takes it."""
    return asdict(style)
