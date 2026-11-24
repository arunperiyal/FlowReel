"""The second tutorial's pictures, from its project built on the real data.

    python examples/tutorial_unsteady/stills.py PROJECT [-o docs/tutorials/unsteady/images]

``PROJECT`` is the tutorial's project at the end of chapter 5: the shot rendered at the
size of its box, ``panel draw`` run, ``scene preview board --at 1.5 4`` run, ``film.mp4``
and ``contact.png`` built. The
data (Zenodo record 5039610) is CC BY 4.0, so the pictures may be kept and shown, with
its credit on the tutorial's pages.

| File | Chapter | What |
|---|---|---|
| ``02-shot.png`` | 2 | frames 0 and 100 of ``wake``, side by side |
| ``03-panel.png`` | 3 | frame 150 of the panel ``force`` |
| ``04-layout.png`` | 4 | ``scene preview board --at 1.5 4``: the caption, then the freeze |
| ``05-check.png`` | 5 | the contact sheet of ``film check`` |
| ``film.gif`` | index | the film, small and at 8 frames a second |
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
IMAGES = HERE.parent.parent / "docs" / "tutorials" / "unsteady" / "images"
sys.path.insert(0, str(HERE.parent / "tutorial"))
from stills import WIDTH, frame, row, still  # noqa: E402  (the first tutorial's helpers)


def stills(project: str | Path, out: str | Path = IMAGES) -> list[Path]:
    """Write the pictures (see the module); returns the files written."""
    from PIL import Image

    from flowreel.film import ffmpeg
    project, out = Path(project), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    pictures = {
        "02-shot.png": row([frame(project, "wake", 0), frame(project, "wake", 100)]),
        "03-panel.png": row([frame(project, "force", 150)], width=WIDTH // 3),
        "04-layout.png": row([still(project, "board", 1.5), still(project, "board", 4)]),
        "05-check.png": row([Image.open(project / "contact.png").convert("RGB")]),
    }
    written = []
    for name, picture in pictures.items():
        picture.save(out / name, optimize=True)
        written.append(out / name)
    gif = out / "film.gif"
    ffmpeg.run("-i", str(project / "film.mp4"), "-filter_complex",
               "fps=8,scale=480:-2:flags=lanczos,split[a][b];"
               "[a]palettegen=max_colors=96[p];[b][p]paletteuse=dither=bayer",
               "-loop", "0", str(gif))
    written.append(gif)
    return written


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("project", metavar="PROJECT", help="the tutorial project, built")
    parser.add_argument("-o", "--out", default=str(IMAGES), metavar="DIR",
                        help="where the pictures go (default docs/tutorials/unsteady/images/)")
    args = parser.parse_args(argv)
    try:
        for path in stills(args.project, args.out):
            print(f"wrote {path} ({path.stat().st_size / 1000:.0f} kB)")
    except (OSError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
