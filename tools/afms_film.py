"""Write the AFMS film's own FlowReel files, taken from the prototype's scripts.

Usage: python tools/afms_film.py OUT [--prototype DIR] [--force] [--reveal CASE]

The AFMS film was built by ``prototype/afms/make_film.py`` (its shot list, ``SHOTS``,
and settings) and ``prototype/afms/film_text.toml`` (every word, its timing and place,
the freezes, the card, the music). This writes the same film as FlowReel files into
the project folder ``OUT``:

- ``film.yml``: the shots in order, with their rates, fades, freezes and audio;
- ``text/<shot>.yml``: each shot's captions, and ``text/<shot>_freeze_<k>.yml`` each
  freeze's (arrows become ``arrow`` shapes);
- ``cards/opening.yml``: the opening card (logo, title, divider, names);
- ``compare.yml``, ``plots.yml`` and ``flowreel.yml``: the comparison as a layout, the
  two wakes stacked and the live plots of mid-span displacement, lift and drag on the
  right as a ``rate: output`` panel, read from the cases' series CSV.

OUT is meant to live with the research data, outside this repository, because the
files name the logo and the licensed music. Nothing here copies them, or any frame.
The folder then needs (paths as the prototype had them):

- ``frames/``: the prototype's frame folders (``bare_domain``, ``bare_reveal``,
  ``carve``, ``helical_reveal``, ``bare_panel``, ``helical_panel``, ``top``,
  ``slices``, ``helical_section``, ``wall``, ``liftmap``);
- ``series/bare_series.csv`` and ``series/helical_series.csv`` (``extract_series.py``);
- the logo and the track at the paths the prototype names (``assets/``).

``--reveal CASE`` also writes ``OUT/reveal/``: the bare reveal as a FlowReel shot
(``bare_reveal.yml`` and ``cameras.yml``, from the prototype's ``render_frames.py``:
camera, crop, wake, colours and the sweep, timed by ``make_film.py``'s ``REVEAL``) and,
when the case is there, its ``flowreel.yml`` (``project init``). Phase 5 renders it on
airavata with ``flowreel shot render bare_reveal.yml --submit``.

``tests/test_golden_film.py`` runs this into a temporary folder with generated frame
folders of the film's counts, and checks lengths and captions against the prototype.
Not part of the package.
"""
from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PROTOTYPE = ROOT / "prototype" / "afms"
#: Written for the film's audio; film_text.toml says it in a comment.
LICENCE = "Pixabay Content License"
#: The prototype's default arrow width (make_film.caption_image).
ARROW_WIDTH = 4
HEADER = ("# The AFMS film, written for FlowReel by tools/afms_film.py from the prototype's\n"
          "# make_film.py and film_text.toml. Edit here from now on.\n")


class Dumper(yaml.SafeDumper):
    """YAML as a person writes it: lists of numbers or words in one line, and mappings
    of those (an arrow) too."""


def _flat(value) -> bool:
    return isinstance(value, (int, float, str, bool)) or value is None


def _list(dumper, data):
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data,
                                     flow_style=all(_flat(v) for v in data))


def _dict(dumper, data):
    flow = all(_flat(v) or (isinstance(v, list) and all(_flat(x) for x in v))
               for v in data.values()) and "lines" not in data and len(data) <= 3
    return dumper.represent_mapping("tag:yaml.org,2002:map", data.items(), flow_style=flow)


Dumper.add_representer(list, _list)
Dumper.add_representer(dict, _dict)


def prototype(folder: Path = PROTOTYPE):
    """The prototype's ``make_film`` module and its ``film_text.toml``, from ``folder``
    (one folder per process: the module is imported once)."""
    folder = Path(folder).resolve()
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    import make_film
    if Path(make_film.__file__).resolve().parent != folder:
        raise RuntimeError(f"make_film was imported from {make_film.__file__}, not {folder}")
    with open(folder / "film_text.toml", "rb") as f:
        return make_film, tomllib.load(f)


def caption(c: dict, freeze: bool = False) -> dict:
    """A ``[[caption]]`` (or a ``[[freeze]]``'s text) of film_text.toml as a FlowReel
    caption. A freeze's caption keeps FlowReel's default times, which are the
    prototype's (0.3 s after the freeze starts to 0.2 s before it ends)."""
    out = {"lines": list(c["lines"])}
    if not freeze:
        out["at"] = [c.get("start", 0), c["end"]] if "end" in c else c.get("start", 0)
    for key in ("place", "size", "align", "colour", "box"):
        if key in c:
            out[key] = c[key]
    width = c.get("arrow_width", ARROW_WIDTH)
    shapes = []
    for x1, y1, x2, y2 in c.get("arrows", []):
        arrow = {"from": [x1, y1], "to": [x2, y2]}
        if width != ARROW_WIDTH:
            arrow["width"] = width
        shapes.append({"arrow": arrow})
    if shapes:
        out["shapes"] = shapes
    return out


def flow_times(mf) -> list[float]:
    """The physical time of each flow frame of the comparison: one per saved step from
    ``T1`` to ``T2``, ``STEP`` steps apart, in ``tU/D``."""
    return [round((mf.T1 + mf.STEP * i) * mf.DT, 6)
            for i in range((mf.T2 - mf.T1) // mf.STEP + 1)]


def write(out: Path, force: bool = False, folder: Path = PROTOTYPE) -> list[Path]:
    """Write the AFMS film's FlowReel files, from the prototype in ``folder``, into
    ``out``; returns the files written. Existing files are kept unless ``force``."""
    mf, text = prototype(folder)
    look = text.get("style", {})     # the final version's typeface: [style] font, maths
    files: dict[str, tuple[str, object]] = {}

    def put(name, data, note=""):
        files[name] = (HEADER + (note and f"# {note}\n"), data)

    shots = []
    for shot in mf.SHOTS:
        name = shot["name"]
        s = {"name": name}
        if "card" in shot:
            s["card"] = f"cards/{shot['card']}.yml"
            s["seconds"] = text[shot["card"]]["seconds"]
        elif "hold" in shot:
            s["hold_last_of"] = shot["hold"]
            s["seconds"] = shot["seconds"]
        elif shot.get("plots"):
            s["layout"] = "compare.yml"
        else:
            s["frames"] = f"frames/{shot['frames']}"
        if "fps" in shot and shot["fps"] != mf.FPS:
            s["rate"] = {"fps": shot["fps"],
                         "to_output": "interpolate" if shot.get("smooth", True) else "repeat"}
        freezes = sorted((f for f in text.get("freeze", []) if f["shot"] == name),
                         key=lambda f: f["at"])
        if freezes:
            s["freezes"] = []
            for k, f in enumerate(freezes, start=1):
                entry = {"at": f["at"], "hold": f["hold"]}
                if f.get("lines"):
                    entry["text"] = f"text/{name}_freeze_{k}.yml"
                    put(entry["text"], [caption(f, freeze=True)],
                        f"The text of {name}'s freeze {k}, shown while it holds.")
                s["freezes"].append(entry)
        fade = list(shot.get("fade", (0, 0)))
        if any(fade):
            s["fade"] = fade
        if "fade_out_at" in shot:
            s["fade_out_at"] = shot["fade_out_at"]
        captions = [caption(c) for c in text.get("caption", []) if c["shot"] == name]
        if captions:
            s["text"] = f"text/{name}.yml"
            put(s["text"], captions, f"The captions of shot {name}.")
        shots.append(s)

    audio = text.get("audio")
    film = {"output": "film.mp4", "fps": mf.FPS, "size": list(mf.SIZE),
            "style": {"colours": {"text": mf.WHITE, "muted": mf.MUTED},
                      "caption": {"size": 50, "shadow": True, "fade": mf.CAPTION_FADE,
                                  "margin": mf.CAPTION_MARGIN}}}
    if "font" in look:
        film["style"] = {"font": look["font"], "maths": look.get("maths", "font"), **film["style"]}
    if audio:
        film["audio"] = [{"file": audio["file"], "offset": audio.get("start", 0),
                          "volume": audio.get("volume", 1.0),
                          "fade": [audio.get("fade_in", 1), audio.get("fade_out", 3)],
                          "licence": LICENCE}]
    film["shots"] = shots
    put("film.yml", film)

    opening = text["opening"]
    put("cards/opening.yml", {"background": "black", "blocks": [
        {"image": "../" + mf.LOGO.relative_to(mf.ROOT).as_posix(), "height": mf.LOGO_HEIGHT,
         "y": 110},
        {"title": list(opening["title"]), "size": 60, "spacing": 82, "gap": 70},
        {"divider": 320, "thickness": 2, "gap": 38},
        {"heading": "CREATED BY", "names": list(opening["created_by"]), "gap": 46},
        {"heading": "CO-AUTHORED BY", "names": list(opening["coauthors"]), "gap": 26}]},
        "The opening card: the logo, the title and the names.")

    times = flow_times(mf)
    put("compare.yml", {"size": list(mf.SIZE), "tiles": [
        {"frames": "frames/bare_panel", "at": [0, 0], "size": [1280, 540]},
        {"frames": "frames/helical_panel", "at": [0, 540], "size": [1280, 540]},
        {"panel": "plots.yml", "rate": "output", "at": [1280, 0], "size": [640, 1080]}]},
        "The comparison: the two wakes stacked on the left, the live plots on the right.")
    cases, labels = text["cases"], text["plots"]

    def lines(column):
        return [{"body": case, "series": "motion", "column": column,
                 **({"label": cases[case]["name"]} if column == "y" else {}),
                 "colour": cases[case]["colour"]} for case in ("bare", "helical")]
    put("plots.yml", {
        "type": "series", "size": [640, 1080], "times": times,
        "x": {"label": labels["time"], "range": [times[0], times[-1]]},
        "rows": [{"label": labels["displacement"], "lines": lines("y")},
                 {"label": labels["lift"], "lines": lines("cl")},
                 {"label": labels["drag"], "lines": lines("cd")}],
        "margins": {"left": 0.2, "right": 0.95, "top": 0.93, "bottom": 0.08, "space": 0.18},
        **({"style": {"font": look["font"],     # panels have no maths: font, so only a set
                      **({"maths": look["maths"]} if look.get("maths", "font") != "font" else {})}}
           if "font" in look else {})},
        "The live plots: mid-span displacement, lift and drag of both cases, to each time.")
    put("flowreel.yml", {"bodies": {case: {"series": {"motion": {
        "file": f"series/{case}_series.csv", "time": "t",
        "columns": {"y": "y_over_D", "cl": "CL", "cd": "CD"}}}} for case in ("bare", "helical")}},
        "The two cases, with their series from the prototype's extract_series.py.")

    written = []
    for name, (head, data) in files.items():
        path = out / name
        if path.exists() and not force:
            raise FileExistsError(f"{path} exists (use --force to overwrite)")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(head + yaml.dump(data, Dumper=Dumper, sort_keys=False,
                                         allow_unicode=True, width=88), encoding="utf-8")
        written.append(path)
    return written


def reveal_shot(case: str | Path, folder: Path = PROTOTYPE) -> tuple[str, str]:
    """The bare reveal as a FlowReel shot file and its ``cameras.yml``, from the
    prototype's ``render_frames.py`` (look) and ``make_film.py`` (steps, the sweep's
    frames). The case is the bare case's folder."""
    mf, _ = prototype(folder)
    import render_frames as rf
    first, last = mf.REVEAL                           # frames of the sweep, at 8 fps
    span = last - first
    (x0, x1), (y0, y1), (z0, z1) = rf.CROP
    position, focal, up = rf.CAMERA
    lo, hi = rf.COLOUR_RANGE
    field = {"xVor_true": "vorticity_x", "zVor_true": "vorticity_z"}[rf.COLOUR_FIELD]
    shot = f"""{HEADER.rstrip()}
# The bare reveal: the coloured wake, then from frame {first} to {last} a cutting plane sweeps
# along the span to mid-span, showing a live section, and the wake turns grey. One frame
# per saved step, {mf.T1} to {mf.T2} ({rf.__file__.rsplit('/', 1)[-1]}, --look reveal).
name: bare_reveal
source: bare
time: {{steps: [{mf.T1}, {mf.T2}], every: 1}}
crop: {{x: [{x0}, {x1}], y: [{y0}, {y1}], z: [{z0}, {z1}]}}
camera: {{view: main}}
size: [{rf.SIZE[0]}, {rf.SIZE[1]}]
background: black
antialias: ssaa
layers:
  - {{type: body}}
  - type: slice
    normal: x
    position: &sweep {{from: {rf.SWEEP_START}, to: {rf.MIDSPAN}, frames: [{first}, {last}]}}
    field: {field}
    range: [{lo}, {hi}]
    opacity: {{from: 0.0, to: 1.0, frames: [{first}, {first + 0.1 * span:g}]}}
    fade_weak: [0.05, 0.5]
    near_wall: [0.03, 0.1]
  - type: iso
    field: {rf.WAKE_FIELD}
    level: {rf.WAKE_LEVEL}
    wall_gap: {rf.WALL_GAP}
    colour_by: {field}
    range: [{lo}, {hi}]
    clip_axis: x
    clip_position: *sweep
    clip_keep: above
    clip_active: {{keys: [[0, false], [{first + 0.01:g}, true]]}}
    grey: {{from: 0.0, to: 1.0, frames: [{first + 0.4 * span:g}, {last}]}}
    grey_colour: "{rf.MUTED}"
"""
    cameras = (f"{HEADER.rstrip()}\nviews:\n  - {{name: main, position: {list(position)}, "
               f"focal: {list(focal)}, up: {list(up)}, view_angle: {rf.VIEW_ANGLE}}}\n")
    return shot, cameras


def write_reveal(out: Path, case: str | Path, force: bool = False,
                 folder: Path = PROTOTYPE) -> list[Path]:
    """Write ``out/reveal/``: the reveal shot, its cameras and, when ``case`` is there,
    its ``flowreel.yml`` and the case as the tag ``bare``; returns the files written."""
    shot, cameras = reveal_shot(case, folder)
    target = Path(out) / "reveal"
    target.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in (("bare_reveal.yml", shot), ("cameras.yml", cameras)):
        path = target / name
        if path.exists() and not force:
            raise FileExistsError(f"{path} exists (use --force to overwrite)")
        path.write_text(text)
        written.append(path)
    if (Path(case) / "binary").is_dir():
        from flowreel.project.imports import import_data
        from flowreel.project.init import init_project
        written.append(init_project(target, force=force))
        written.append(import_data(target, "plt", str(Path(case) / "binary"), "bare", force=force).domain)
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out", type=Path, help="the AFMS project folder")
    parser.add_argument("--prototype", type=Path, default=PROTOTYPE, metavar="DIR",
                        help="the folder of make_film.py and film_text.toml "
                             "(default: prototype/afms in this repository)")
    parser.add_argument("--force", action="store_true", help="overwrite files that exist")
    parser.add_argument("--reveal", metavar="CASE",
                        help="also write reveal/: the bare reveal as a shot of the case CASE")
    args = parser.parse_args()
    for path in write(args.out, args.force, args.prototype):
        print(path)
    if args.reveal:
        for path in write_reveal(args.out, args.reveal, args.force, args.prototype):
            print(path)


if __name__ == "__main__":
    main()
