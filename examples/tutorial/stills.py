"""The tutorial's pictures: a still for each chapter and a short GIF of the film.

    python examples/tutorial/stills.py PROJECT [-o docs/tutorials/steady/images]

``PROJECT`` is a tutorial project at the end of chapter 9: its shots rendered at the size
of their boxes, ``panel draw`` run, the scenes previewed as chapters 7 and 8 say, and
``film.mp4`` and ``contact.png`` built. The pictures are made from those files,
so they show what a reader's own project shows, from the real data set
(``cylinder_crossflow``, Apache-2.0: its licence allows them to be shown and kept in
the repository; docs/tutorials/steady/data.md).

Written into ``-o`` (default ``docs/tutorials/steady/images/`` of this repository):

| File | Chapter | What |
|---|---|---|
| ``03-first-shot.png`` | 3 | frame 0 of ``wake`` as chapter 3 has it, from the view ``main`` |
| ``04-camera.png`` | 4 | frames 0 and 96 of ``wake``, side by side |
| ``05-sweep.png`` | 5 | frames 0, 48 and 71 of ``sweep`` |
| ``06-panel.png`` | 6 | frame 0 of ``pressure`` |
| ``07-scene.png`` | 7 | ``scene preview wake --at 2 5.5``: the caption, then the freeze |
| ``08-layout.png`` | 8 | ``scene preview compare --at 1 4.5`` and ``title --at 2`` |
| ``09-check.png`` | 9 | the contact sheet of ``film check`` |
| ``film.gif`` | index | the film, small and at 8 frames a second |

Stills are 960 pixels wide in all, so the repository stays small.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
IMAGES = HERE.parent.parent / "docs" / "tutorials" / "steady" / "images"
WIDTH = 960
GIF = {"width": 480, "fps": 8}


def frame(project: Path, shot: str, index: int) -> Image.Image:
    """Frame ``index`` of the full-size frames of ``shot``."""
    path = project / "frames" / shot / f"frame_{index:05d}.png"
    if not path.is_file():
        raise FileNotFoundError(f"{path}: render the tutorial's shots first (chapters 7 "
                                f"and 8)")
    return Image.open(path).convert("RGB")


def chapter3(project: Path) -> Image.Image:
    """Frame 0 of ``wake`` as chapter 3 leaves it, before chapter 4 gives it a track:
    drawn from the view ``main``, which ``project init`` wrote."""
    import yaml
    from flowreel.scene.rendering import render_frame
    shot = yaml.safe_load((project / "shots" / "wake.yml").read_text())
    shot["camera"] = {"view": "main"}
    path = project / "shots" / ".chapter3_wake.yml"   # beside it: paths stay right
    path.write_text(yaml.safe_dump(shot, sort_keys=False))
    try:
        return Image.fromarray(render_frame(path, 0))
    finally:
        path.unlink()


def still(project: Path, scene: str, at: float) -> Image.Image:
    """The still ``scene preview SCENE --at AT`` wrote."""
    path = project / "frames" / "scenes" / scene / f"at_{at:.2f}.png"
    if not path.is_file():
        raise FileNotFoundError(f"{path}: run flowreel scene preview {scene} --at {at:g} "
                                f"first (chapters 7 and 8)")
    return Image.open(path).convert("RGB")


def row(images: list[Image.Image], width: int = WIDTH, gap: int = 8) -> Image.Image:
    """``images`` side by side, scaled to ``width`` in all, ``gap`` pixels apart."""
    each = (width - gap * (len(images) - 1)) // len(images)
    scaled = [im.resize((each, round(im.height * each / im.width)), Image.LANCZOS)
              for im in images]
    out = Image.new("RGB", (width, max(im.height for im in scaled)), "white")
    for k, im in enumerate(scaled):
        out.paste(im, (k * (each + gap), 0))
    return out


def stills(project: str | Path, out: str | Path = IMAGES) -> list[Path]:
    """Write the stills and the GIF (see the module); returns the files written."""
    from flowreel.film import ffmpeg
    project, out = Path(project), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pictures = {
        "03-first-shot.png": row([chapter3(project)]),
        "04-camera.png": row([frame(project, "wake", 0), frame(project, "wake", 96)]),
        "05-sweep.png": row([frame(project, "sweep", i) for i in (0, 48, 71)]),
        "06-panel.png": row([frame(project, "pressure", 0)]),
        "07-scene.png": row([still(project, "wake", 2), still(project, "wake", 5.5)]),
        "08-layout.png": row([still(project, "compare", 1), still(project, "compare", 4.5),
                              still(project, "title", 2)]),
        "09-check.png": row([Image.open(project / "contact.png").convert("RGB")]),
    }
    written = []
    for name, picture in pictures.items():
        picture.save(out / name, optimize=True)
        written.append(out / name)
    gif = out / "film.gif"
    w, fps = GIF["width"], GIF["fps"]
    ffmpeg.run("-i", str(project / "film.mp4"), "-filter_complex",
               f"fps={fps},scale={w}:-2:flags=lanczos,split[a][b];"
               f"[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
               "-loop", "0", str(gif))
    written.append(gif)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", metavar="PROJECT", help="the tutorial project, built")
    parser.add_argument("-o", "--out", default=str(IMAGES), metavar="DIR",
                        help="where the pictures go (default docs/tutorials/steady/images/)")
    args = parser.parse_args(argv)
    try:
        for path in stills(args.project, args.out):
            print(f"wrote {path} ({path.stat().st_size / 1000:.0f} kB)")
    except (OSError, RuntimeError) as exc:      # RuntimeError: ffmpeg failed
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
