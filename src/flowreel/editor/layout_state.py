"""What the scene design window knows, without a window (plan Section 19.11).

:class:`DesignState` edits the layout of one scene of a film of scenes: its boxes as the
YAML mappings they are written as (so a box's keys the window does not touch are kept),
in the film's pixels. Every change is checked by the layout's own reader
(:func:`flowreel.film.model.parse_layout`) and written at once: to the layout's file
(``layouts/NAME.yml``), or for a layout written in place, to that scene's ``layout:``
block of ``film.yml``, the rest of the file and its comments as they were. A change the
reader refuses is not made, and its message says why. Closing the window, or a crash,
loses nothing.

=============  =========================================================================
Action         Does
=============  =========================================================================
``add``        a new text box over a rectangle drawn (to be named and filled)
``move``       a box by an offset, its edges or centre snapped
``resize``     a box by one corner, the corner snapped
``rename``     a box (and every ``follow`` naming it)
``fill``       a box with one kind of content, in place of what it had
``remove``     a box
``undo``       goes back one change, and writes the file again
=============  =========================================================================

**Snapping.** A moved edge (or centre) within :data:`TOLERANCE` pixels of an edge or the
centre of another box, or of the frame, goes there; otherwise to the grid, when there is
one (``grid`` pixels; ``0`` for none).

**Where a box is.** A box at ``place`` is given ``pos`` and ``size`` once it is moved or
resized. A text box at ``pos`` alone is as large as its text, measured. A box that
follows a point of the flow is placed by the flow, so it is not moved by hand.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from flowreel.film import model as M
from flowreel.scene.errors import Checker, ConfigError

#: Pixels within which an edge snaps to another edge or centre.
TOLERANCE = 8.0
#: The smallest box drawn or resized, pixels.
MINIMUM = 8.0
#: What a new box shows until it is filled.
NEW_TEXT = "Text"
#: The corners a box is resized by.
CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


class DesignError(ValueError):
    """A change that cannot be made (the message says why)."""


@dataclass
class DesignState:
    """The layout of scene ``scene`` of the film at ``film_path``: its ``boxes`` (the
    YAML mappings), ``background`` (``None`` when not written), where it is written
    (``layout_file``, or ``None``: in place in ``film.yml``), the film's ``size`` and
    ``fps``, the ``grid`` snapped to, the ``selected`` box's name, and the ``history``
    of earlier states for :meth:`undo`. Build with :meth:`open`."""

    film_path: Path
    scene: str
    boxes: list
    background: object
    layout_file: Path | None
    size: tuple[int, int]
    fps: int
    grid: float = 20.0
    selected: str | None = None
    history: list = field(default_factory=list)
    message: str = ""

    @classmethod
    def open(cls, film_path, scene: str, grid: float = 20.0) -> "DesignState":
        """The state of scene ``scene`` of the film of scenes at ``film_path``."""
        from flowreel.yamlfile import read_yaml
        film_path = Path(film_path)
        film = M.load(film_path)                  # checked whole before anything is edited
        film.scene(scene)
        data = read_yaml(film_path)
        spec = next(s for s in data["scenes"] if s.get("name") == scene)
        layout = spec["layout"]
        if isinstance(layout, str):
            file = M.layout_path(layout, film_path.parent)
            raw = read_yaml(file)
        else:
            file, raw = None, layout
        return cls(film_path, scene, copy.deepcopy(raw["boxes"]), raw.get("background"),
                   file, film.size, film.fps, grid)

    # -- reading ---------------------------------------------------------------------

    @property
    def folder(self) -> Path:
        """Where the layout's paths start: its file's folder, or the film file's."""
        return (self.layout_file or self.film_path).parent

    def raw(self) -> dict:
        """The layout as it is written."""
        out = {} if self.background is None else {"background": self.background}
        out["boxes"] = self.boxes
        return out

    def layout(self, boxes=None, background=None) -> M.Layout:
        """The layout read (checked) as the film would read it; ``boxes`` and
        ``background`` replace the current ones (to check a change before making it)."""
        raw = self.raw()
        if boxes is not None:
            raw["boxes"] = boxes
        if background is not None:
            raw["background"] = background
        where = Checker(self.layout_file) if self.layout_file else \
            Checker(self.film_path, ("scenes", self.scene, "layout"))
        return M.parse_layout(raw, where, self.folder, self.fps, self.size, self.layout_file)

    def names(self) -> list[str]:
        """The boxes' names, in drawing order."""
        return [b.name for b in self.layout().boxes]

    def index(self, name: str) -> int:
        """The position of box ``name`` in :attr:`boxes`."""
        names = self.names()
        if name not in names:
            raise DesignError(f"no box {name!r} (boxes: {', '.join(names)})")
        return names.index(name)

    def rect(self, name: str) -> tuple[float, float, float, float]:
        """Box ``name``'s rectangle ``(x, y, w, h)`` in the film's pixels (a text at
        ``pos`` alone measured; a box that follows a point: a small square at its
        ``offset``, for showing it)."""
        box = self.layout().boxes[self.index(name)]
        r = box.rect(self.size)
        if r is not None:
            return tuple(float(v) for v in r)
        if box.follow is not None:
            w, h = box.size or (40.0, 40.0)
            return (0.0, 0.0, float(w), float(h))
        from flowreel.film.boxes import text_image
        from flowreel.film.model import Style
        _, (left, top, right, bottom) = text_image(box.content.lines, box.content.drawn,
                                                   Style(), self.size, corner=box.pos)
        return (box.pos[0], box.pos[1], max(right - left, MINIMUM), max(bottom - top, MINIMUM))

    def at(self, x: float, y: float) -> str | None:
        """The name of the top box at ``(x, y)``, or ``None``."""
        for name in reversed(self.names()):
            bx, by, bw, bh = self.rect(name)
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return name
        return None

    # -- snapping --------------------------------------------------------------------

    def targets(self, axis: int, skip: str | None = None) -> list[float]:
        """Edges and centres to snap to along ``axis`` (0: x, 1: y): the frame's and
        every box's but ``skip``."""
        span = self.size[axis]
        out = [0.0, span / 2, float(span)]
        for name in self.names():
            if name == skip:
                continue
            r = self.rect(name)
            lo, length = r[axis], r[axis + 2]
            out += [lo, lo + length / 2, lo + length]
        return out

    def snap(self, value: float, axis: int, skip: str | None = None) -> float:
        """``value`` snapped (see the module)."""
        near = min(self.targets(axis, skip), key=lambda t: abs(t - value))
        if abs(near - value) <= TOLERANCE:
            return near
        if self.grid:
            return round(value / self.grid) * self.grid
        return value

    def _snap_span(self, lo: float, length: float, axis: int, skip: str) -> float:
        """Where a span of ``length`` starting at ``lo`` goes: its start, centre or end
        snapped to the nearest edge (the grid otherwise, by its start)."""
        best = None
        for t in self.targets(axis, skip):
            for offset in (0.0, length / 2, length):
                shift = t - (lo + offset)
                if abs(shift) <= TOLERANCE and (best is None or abs(shift) < abs(best)):
                    best = shift
        if best is not None:
            return lo + best
        return round(lo / self.grid) * self.grid if self.grid else lo

    # -- changes ---------------------------------------------------------------------

    def _change(self, boxes: list, what: str, select: str | None = "keep") -> None:
        try:
            self.layout(boxes)
        except ConfigError as exc:
            raise DesignError(str(exc)) from None
        self.history.append((copy.deepcopy(self.boxes), self.selected))
        self.boxes = boxes
        if select != "keep":
            self.selected = select
        self.write()
        self.message = what

    def _free_name(self, base: str) -> str:
        names = set(self.names())
        k = 1
        while f"{base}{k}" in names:
            k += 1
        return f"{base}{k}"

    def add(self, x0: float, y0: float, x1: float, y1: float, name: str | None = None) -> str:
        """A new text box over the rectangle from ``(x0, y0)`` to ``(x1, y1)``, its
        corners snapped; returns its name."""
        xs = sorted((self.snap(x0, 0), self.snap(x1, 0)))
        ys = sorted((self.snap(y0, 1), self.snap(y1, 1)))
        if xs[1] - xs[0] < MINIMUM or ys[1] - ys[0] < MINIMUM:
            raise DesignError(f"a box is at least {MINIMUM:g} pixels each way")
        name = name or self._free_name("box")
        box = {"name": name, "text": NEW_TEXT, "pos": [_n(xs[0]), _n(ys[0])],
               "size": [_n(xs[1] - xs[0]), _n(ys[1] - ys[0])]}
        self._change([*copy.deepcopy(self.boxes), box], f"added {name}", select=name)
        return name

    def _placed(self, name: str) -> tuple[list, dict]:
        """The boxes copied, and box ``name``'s copy, with ``pos`` and ``size`` written
        (from ``place`` or its measured text) so it can be moved."""
        boxes = copy.deepcopy(self.boxes)
        box = boxes[self.index(name)]
        if box.get("follow") is not None:
            raise DesignError(f"box {name!r} follows a point of the flow: it is placed by "
                              "the flow, not by hand (edit its follow offset)")
        x, y, w, h = self.rect(name)
        box.pop("place", None)
        box["pos"], box["size"] = [_n(x), _n(y)], [_n(w), _n(h)]
        return boxes, box

    def move(self, name: str, dx: float, dy: float) -> None:
        """Move box ``name`` by ``(dx, dy)`` pixels, snapped."""
        boxes, box = self._placed(name)
        (x, y), (w, h) = box["pos"], box["size"]
        box["pos"] = [_n(self._snap_span(x + dx, w, 0, name)), _n(self._snap_span(y + dy, h, 1, name))]
        self._change(boxes, f"moved {name} to {box['pos']}", select=name)

    def resize(self, name: str, corner: str, x: float, y: float) -> None:
        """Move corner ``corner`` (:data:`CORNERS`) of box ``name`` to ``(x, y)``,
        snapped; the opposite corner stays."""
        if corner not in CORNERS:
            raise DesignError(f"a corner is one of {', '.join(CORNERS)}")
        boxes, box = self._placed(name)
        (bx, by), (w, h) = box["pos"], box["size"]
        left, top, right, bottom = bx, by, bx + w, by + h
        x, y = self.snap(x, 0, name), self.snap(y, 1, name)
        if "left" in corner:
            left = min(x, right - MINIMUM)
        else:
            right = max(x, left + MINIMUM)
        if "top" in corner:
            top = min(y, bottom - MINIMUM)
        else:
            bottom = max(y, top + MINIMUM)
        box["pos"], box["size"] = [_n(left), _n(top)], [_n(right - left), _n(bottom - top)]
        self._change(boxes, f"resized {name} to {box['size']}", select=name)

    def rename(self, old: str, new: str) -> None:
        """Rename box ``old`` to ``new``, and every ``follow`` naming it."""
        new = new.strip()
        if not new:
            raise DesignError("a box's name is a word")
        if new in self.names() and new != old:
            raise DesignError(f"box {new!r} exists already")
        boxes = copy.deepcopy(self.boxes)
        boxes[self.index(old)]["name"] = new
        for b in boxes:
            if isinstance(b.get("follow"), dict) and b["follow"].get("box") == old:
                b["follow"]["box"] = new
        self._change(boxes, f"renamed {old} to {new}", select=new)

    def fill(self, name: str, kind: str, value: str) -> None:
        """Box ``name`` shows ``kind`` (:data:`~flowreel.film.model.KINDS`) from one line
        ``value``: a text's lines (``|`` between lines), a file (image, shot, panel), a
        shape's kind, or a scene's name (``last_frame``). Its other content goes; a
        mapping it had for the same kind keeps its other options."""
        if kind not in M.KINDS:
            raise DesignError(f"a box shows one of {', '.join(M.KINDS)}, not {kind!r}")
        boxes = copy.deepcopy(self.boxes)
        box = boxes[self.index(name)]
        old = box.get(kind)
        for k in M.KINDS:
            box.pop(k, None)
        value = value.strip()
        if kind == "text":
            lines = [line.strip() for line in value.split("|")]
            short = lines[0] if len(lines) == 1 else lines
            box[kind] = {**old, "lines": short} if isinstance(old, dict) else short
        elif kind in ("image", "shot", "panel"):
            box[kind] = {**old, "file": value} if isinstance(old, dict) and "file" in old else value
        elif kind == "shape":
            box[kind] = {**old, "kind": value} if isinstance(old, dict) else value
        else:
            box[kind] = value
        if kind not in ("text", "shape") and "follow" in box:
            box.pop("follow")
        self._change(boxes, f"{name} shows {kind}")

    def remove(self, name: str) -> None:
        """Remove box ``name``."""
        boxes = copy.deepcopy(self.boxes)
        del boxes[self.index(name)]
        if not boxes:
            raise DesignError("a layout keeps at least one box")
        self._change(boxes, f"removed {name}", select=None)

    def undo(self) -> None:
        """Go back one change."""
        if not self.history:
            raise DesignError("nothing to undo")
        self.boxes, self.selected = self.history.pop()
        self.write()
        self.message = "undone"

    # -- writing ---------------------------------------------------------------------

    def write(self) -> None:
        """Write the layout where it is written (see the module)."""
        text = yaml.safe_dump(self.raw(), sort_keys=False, default_flow_style=None, width=100)
        if self.layout_file is not None:
            self.layout_file.write_text(text)
            return
        self.film_path.write_text(inline(self.film_path.read_text(), self.scene, self.raw()))


def _n(v: float):
    """A pixel value as written: a whole number when it is one."""
    v = round(float(v), 2)
    return int(v) if v == int(v) else v


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def inline(text: str, scene: str, layout: dict) -> str:
    """``film.yml``'s ``text`` with scene ``scene``'s ``layout:`` block replaced by
    ``layout``, every other line as it was. A scene written in flow style on one line is
    written again whole (its own comments go)."""
    lines = text.splitlines()
    head = re.compile(r"^(\s*)-\s+(?:name:\s*(\S+?)\s*(?:#.*)?$|\{.*\bname:\s*([^,}\s]+))")
    start = None
    for i, line in enumerate(lines):
        m = head.match(line)
        if m and (m.group(2) or m.group(3) or "").strip("'\"") == scene:
            start, item = i, _indent(line)
            break
    if start is None:
        named = re.compile(rf"^(\s*)name:\s*['\"]?{re.escape(scene)}['\"]?\s*(#.*)?$")
        for i, line in enumerate(lines):
            if named.match(line):
                j = i
                while j >= 0 and not lines[j].lstrip().startswith("- "):
                    j -= 1
                start, item = j, _indent(lines[j])
                break
    if start is None:
        raise DesignError(f"no scene {scene!r} written in the film file")
    keys = item + 2
    end = next((i for i in range(start + 1, len(lines))
                if lines[i].strip() and _indent(lines[i]) <= item), len(lines))
    if lines[start].lstrip()[2:].lstrip().startswith("{"):
        # a scene in flow style: write it again in block style
        data = yaml.safe_load("\n".join(lines[start:end]).strip()[1:].strip()) or {}
        data = data if isinstance(data, dict) else {}
        data["layout"] = layout
        block = yaml.safe_dump([data], sort_keys=False, default_flow_style=None, width=100)
        lines[start:end] = [" " * item + b for b in block.rstrip().splitlines()]
        return "\n".join(lines) + "\n"
    first = lines[start].lstrip()[2:]
    at = None
    if re.match(r"layout\s*:", first):
        at = start
    else:
        at = next((i for i in range(start + 1, end)
                   if _indent(lines[i]) == keys and re.match(r"layout\s*:", lines[i].strip())), None)
    dumped = yaml.safe_dump({"layout": layout}, sort_keys=False, default_flow_style=None,
                            width=100).rstrip().splitlines()
    if at is None:
        lines[end:end] = [" " * keys + d for d in dumped]
        return "\n".join(lines) + "\n"
    stop = next((i for i in range(at + 1, end)
                 if lines[i].strip() and _indent(lines[i]) <= keys), end)
    if at == start:
        new = [lines[start][:item] + "- " + dumped[0]] + [" " * keys + d for d in dumped[1:]]
    else:
        new = [" " * keys + d for d in dumped]
    lines[at:stop] = new
    return "\n".join(lines) + "\n"
