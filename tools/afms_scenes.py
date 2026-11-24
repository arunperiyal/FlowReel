"""Write the AFMS film as scenes, from the film of shots it was first written as.

Usage: python tools/afms_scenes.py OLD_DIR OUT_DIR

``OLD_DIR`` is a folder with the film as ``tools/afms_film.py`` wrote it (``film.yml`` of
shots, ``text/*.yml`` caption files, ``cards/opening.yml``, ``compare.yml`` of tiles and
``plots.yml``). ``OUT_DIR`` gets ``film.yml`` (one scene per shot, its captions as text
and arrow boxes at the same pixels and seconds, the opening card as an image and text
boxes, the comparison as two shot boxes and a panel box), ``layouts/`` and
``panels/plots.yml``. The frames, assets and series are linked in by the caller; this tool
only reads and writes YAML. Not part of the package: the film of shots is no longer read,
and this is how the AFMS film left it (Phase 10).
"""
import argparse
import sys
from pathlib import Path

import yaml

HEADER = ("# The AFMS film as scenes, written by tools/afms_scenes.py from the film of shots.\n"
          "# Edit here from now on. Reference: docs/guide/film/film.md.\n")


class Dumper(yaml.SafeDumper):
    """Short lists in flow style (``[0, 0]``), and no anchors."""

    def ignore_aliases(self, data):
        return True


def dump(data) -> str:
    return HEADER + yaml.dump(data, Dumper=Dumper, sort_keys=False, width=100,
                              default_flow_style=None, allow_unicode=True)


def _arrow(shape: dict, at, common: dict) -> dict:
    """An arrow box from ``{arrow: {from, to}}``: its box spans the two points and the tip
    is at ``to``."""
    (x1, y1), (x2, y2) = shape["arrow"]["from"], shape["arrow"]["to"]
    dx, dy = x2 - x1, y2 - y1
    flat = 4                                              # a flat arrow gets a thin box
    if abs(dy) < flat:
        direction, size = ("right" if dx > 0 else "left"), [abs(dx), flat]
        pos = [min(x1, x2), (y1 + y2) / 2 - flat / 2]
    elif abs(dx) < flat:
        direction, size = ("down" if dy > 0 else "up"), [flat, abs(dy)]
        pos = [(x1 + x2) / 2 - flat / 2, min(y1, y2)]
    else:
        vertical = "down" if dy > 0 else "up"
        direction = f"{vertical}_{'right' if dx > 0 else 'left'}"
        size, pos = [abs(dx), abs(dy)], [min(x1, x2), min(y1, y2)]
    kind = {"kind": "arrow", "direction": direction, "shadow": True, **common}
    return {"pos": [round(v, 1) for v in pos], "size": [round(v, 1) for v in size],
            **({"at": at} if at else {}), "shape": kind}


def captions(path: Path, shift: float = 0.0, hold: float | None = None) -> list[dict]:
    """The boxes of a caption file; ``shift`` seconds are added to every ``at``. A caption
    of a freeze has no ``at`` and shows for the ``hold`` seconds from ``shift``."""
    boxes = []
    for c in yaml.safe_load(path.read_text()) or []:
        given = c.get("at")
        if given is None and hold is not None:
            given = [0, hold]
        if isinstance(given, (int, float)):               # a start alone: to the scene's end
            given = [given, None]
        at = [None if t is None else round(t + shift, 3) for t in given] if given is not None else None
        text = {"lines": c["lines"]}
        for key in ("size", "align", "colour", "box"):
            if key in c:
                text[key] = c[key]
        text.setdefault("align", "centre")
        if isinstance(c.get("place"), list) and c["place"][0] == "centre":
            where = {"pos": [0, c["place"][1]], "size": [1920, 300]}   # centred across, from y
            text["valign"] = "top"
        elif isinstance(c.get("place"), list):
            where = {"pos": c["place"]}
        elif c.get("place") in ("top", "bottom", "centre"):    # a named place: a half, or the middle
            where = {"place": c["place"]}
            text["valign"] = c["place"]
        else:                                              # the captions' default: low, centred
            where = {"place": "bottom"}
            text["valign"] = "bottom"
        boxes.append({**where, **({"at": at} if at else {}), "text": text})
        look = {"colour": c["colour"]} if "colour" in c else {}
        for shape in c.get("shapes", []):
            boxes.append(_arrow(shape, at, look))
    return boxes


def opening() -> list[dict]:
    """The opening card as boxes: the logo, the title, a divider and the names."""
    centre = {"align": "centre", "valign": "top"}
    return [
        {"pos": [660, 110], "size": [600, 190], "image": "assets/iitkgp_logo_white.png"},
        {"pos": [0, 370], "size": [1920, 180],
         "text": {"lines": ["Effect of Helical Groove on Suppression of",
                            "Vortex-Induced Vibration in Flexible Cylinders"],
                  "look": "title", "size": 60, "spacing": 1.37, **centre}},
        {"pos": [800, 590], "size": [320, 2], "shape": {"kind": "line", "width": 2}},
        {"pos": [0, 640], "size": [1920, 40],
         "text": {"lines": "CREATED BY", "look": "small", "size": 26, **centre}},
        {"pos": [0, 685], "size": [1920, 50],
         "text": {"lines": "Arun Periyal", "size": 36, **centre}},
        {"pos": [0, 790], "size": [1920, 40],
         "text": {"lines": "CO-AUTHORED BY", "look": "small", "size": 26, **centre}},
        {"pos": [0, 835], "size": [1920, 120],
         "text": {"lines": ["Ritwik Ghoshal, Vaibhav Joshi,",
                            "Abhijeet Sajjan and Arun Jyoti Sarkar"], "size": 36, **centre}},
    ]


def scenes(old: Path) -> list[dict]:
    film = yaml.safe_load((old / "film.yml").read_text())
    out = []
    for shot in film["shots"]:
        name = shot["name"]
        scene = {"name": name}
        boxes = []
        if "card" in shot:
            boxes = opening()
        elif "frames" in shot:
            box = {"frames": shot["frames"]}
            if "rate" in shot:
                box["rate"] = shot["rate"]
            boxes = [{"shot": box}]
        elif "layout" in shot:
            scene["layout"] = shot["layout"].removesuffix(".yml")
            boxes = None                                   # a layout file, written below
        elif "hold_last_of" in shot:
            boxes = [{"last_frame": shot["hold_last_of"]}]
            if "fade_out_at" in shot:          # the held picture fades out early, on its own:
                fade = shot.pop("fade")        # what follows is black, so a caption can sit on it
                boxes[0].update(at=[0, shot["fade_out_at"] + fade[1]], fade=fade)
        if "seconds" in shot:
            scene["seconds"] = shot["seconds"]
        if "fade" in shot:
            scene["fade"] = shot["fade"]
        extra = []
        if "text" in shot:
            extra += captions(old / shot["text"])
        shift = 0.0
        for freeze in shot.get("freezes", []):
            shift += freeze["hold"]
            if "text" in freeze:                           # shown while the frame is held
                at = freeze["at"] + shift - freeze["hold"]
                extra += captions(old / freeze["text"], at, freeze["hold"])
        if boxes is None:
            scene["_extra"] = extra
        else:
            scene["layout"] = {"boxes": boxes + extra}
        out.append((scene, shot))
    return out


def compare(old: Path, extra: list, freezes: list, rate: dict) -> dict:
    """The comparison's layout: its tiles as boxes, then the scene's captions. The layout
    is a file in ``layouts/``, so its paths start there."""
    boxes = []
    for tile in yaml.safe_load((old / "compare.yml").read_text())["tiles"]:
        pos, size = tile["at"], tile["size"]
        if "frames" in tile:
            box = {"frames": "../" + tile["frames"], "rate": rate}
            if freezes:
                box["freezes"] = freezes
            boxes.append({"pos": pos, "size": size, "shot": box})
        else:
            box = {"file": "../panels/" + Path(tile["panel"]).name, "rate": {"fps": rate["fps"]}}
            if freezes:
                box["freezes"] = freezes
            boxes.append({"pos": pos, "size": size, "panel": box})
    return {"boxes": boxes + extra}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    old, out = args.old, args.out
    film = yaml.safe_load((old / "film.yml").read_text())
    (out / "layouts").mkdir(parents=True, exist_ok=True)
    (out / "panels").mkdir(exist_ok=True)
    listed = []
    for scene, shot in scenes(old):
        extra = scene.pop("_extra", None)
        if extra is not None:                              # the comparison
            freezes = [{"at": f["at"], "hold": f["hold"]} for f in shot.get("freezes", [])]
            layout = compare(old, extra, freezes, shot["rate"])
            (out / "layouts" / f"{scene['layout']}.yml").write_text(
                dump(layout))
        listed.append(scene)
    style = film["style"]
    caption = style.pop("caption", {})
    style["looks"] = {"text": {k: v for k, v in caption.items() if k in ("size", "shadow", "fade", "margin")}}
    new = {"output": film["output"], "fps": film["fps"], "size": film["size"], "style": style,
           "audio": film["audio"], "scenes": listed}
    (out / "film.yml").write_text(dump(new))
    plots = yaml.safe_load((old / "plots.yml").read_text())
    for row in plots["rows"]:
        for line in row["lines"]:
            line["body"] = f"{line['body']}.cyl"          # a body of a tag is tag.body
    (out / "panels" / "plots.yml").write_text(dump(plots))
    print(f"wrote {out / 'film.yml'}: {len(listed)} scenes")


if __name__ == "__main__":
    sys.exit(main())
