"""Body names through a project's declarations (plan Section 5.4).

:class:`DeclaredSource` wraps a source so that everything asking it for a body by name
(layers, the camera's ``follow``, wall fields through ``source.body(step, name)``) uses
the names of ``flowreel.yml``: a declared name is read as its ``zone``. Undeclared zones
keep their own names, so no declaration is needed to draw a body.

:func:`one_body` is the body meant when a name is left out where one body is needed
(``follow: true``): the one declared body, or else the source's only zone.
"""
from __future__ import annotations

import difflib

from flowreel.project.bodies import Body


class DeclaredSource:
    """``source`` seen through the declared ``bodies`` (name to :class:`Body`).

    Every attribute but the body methods is the source's own. It pickles when the
    source does, so a render's worker processes can take it.
    """

    def __init__(self, source, bodies: dict[str, Body]):
        self.source = source
        self.declared = dict(bodies)

    def __getattr__(self, name):
        if name in ("source", "declared", "_series"):   # not yet set (while unpickling)
            raise AttributeError(name)
        return getattr(self.source, name)

    def __getstate__(self):
        return {k: v for k, v in self.__dict__.items() if k != "_series"}

    def __setstate__(self, state):
        self.__dict__.update(state)

    def bodies(self) -> list[str]:
        """Declared names, then the source's zones that no declaration claims."""
        claimed = {b.zone for b in self.declared.values()}
        return list(self.declared) + [z for z in self.source.bodies() if z not in claimed]

    def zone(self, name: str) -> str:
        """The source's zone that ``name`` means: a declared body's ``zone``, or a zone of
        the source by its own name. Raises ``KeyError`` naming the nearest valid name."""
        zones = self.source.bodies()
        if name in self.declared:
            zone = self.declared[name].zone
            if zone not in zones:
                raise KeyError(f"body {name!r} is declared as zone {zone!r}, which "
                               f"{self.source.name} does not have (zones: {', '.join(zones)})")
            return zone
        if name in zones:
            return name
        names = self.bodies()
        close = difflib.get_close_matches(name, names, n=1, cutoff=0.6)
        hint = f"; did you mean {close[0]!r}?" if close else ""
        raise KeyError(f"no body {name!r} (bodies: {', '.join(names)}){hint}")

    def body(self, step: int, name: str | None = None):
        """The wall surface of body ``name`` at ``step``; every body without a name."""
        return self.source.body(step, None if name is None else self.zone(name))

    def series(self, name: str, body: str | None = None):
        """The time series ``name``: the CSV declared under ``body``
        (:func:`flowreel.project.series.read_series`), read once per process.

        Without ``body``: the one declared body with a series ``name``, or else the
        source's own series (flexflow's OTHD and OISD). Raises ``KeyError`` naming what
        there is.
        """
        if body is None:
            owners = [b for b in self.declared.values() if name in b.series]
            if len(owners) > 1:
                raise KeyError(f"series {name!r} is declared for {', '.join(b.name for b in owners)}: "
                               "say which with body=")
            if not owners:
                return self.source.series(name)
            decl = owners[0]
        else:
            decl = self.declaration(body)
            if decl is None:
                self.zone(body)                             # KeyError for an unknown name
                raise KeyError(f"body {body!r} is not declared, so it has no series; "
                               "declare its series in flowreel.yml")
            if name not in decl.series:
                have = ", ".join(decl.series) or "none"
                raise KeyError(f"body {decl.name!r} has no series {name!r} (series: {have})")
        cache = self.__dict__.setdefault("_series", {})
        if (decl.name, name) not in cache:
            from flowreel.project.series import read_series
            cache[(decl.name, name)] = read_series(decl.series[name])
        return cache[(decl.name, name)].copy()

    def declaration(self, name: str) -> Body | None:
        """The :class:`Body` of ``name`` (a body name or a declared zone), or ``None``."""
        if name in self.declared:
            return self.declared[name]
        return next((b for b in self.declared.values() if b.zone == name), None)

    def key(self) -> dict:
        """The declarations as they reach a picture, for frame and surface keys."""
        return {n: b.key() for n, b in sorted(self.declared.items())}


def declare(source, project) -> object:
    """``source`` wrapped with ``project``'s bodies; the source itself when the project
    is ``None``, declares no body, or the source is already wrapped."""
    if project is None or not project.bodies or isinstance(source, DeclaredSource):
        return source
    return DeclaredSource(source, project.bodies)


def one_body(source) -> str:
    """The body meant when a name is left out: the only declared body, or else the
    source's only zone. Raises ``LookupError`` asking for a name otherwise."""
    declared = list(getattr(source, "declared", {})) if isinstance(source, DeclaredSource) else []
    if len(declared) == 1:
        return declared[0]
    names = declared or source.bodies()
    if len(names) == 1:
        return names[0]
    if not names:
        raise LookupError(f"{source.name}: the source has no body")
    raise LookupError(f"name the body: {source.name} has {', '.join(names)}")


def declaration(source, name: str) -> Body | None:
    """The declaration of body ``name`` when ``source`` carries declarations, else ``None``."""
    return source.declaration(name) if isinstance(source, DeclaredSource) else None


def bodies_key(source):
    """The declarations of ``source`` in a key (``None`` for a plain source)."""
    return source.key() if isinstance(source, DeclaredSource) else None
