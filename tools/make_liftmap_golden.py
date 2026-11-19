"""Draw the golden lift-map frame with the prototype's ``render_extras.py liftmap``.

Usage: python tools/make_liftmap_golden.py [--out tests/data/liftmap]

The data are the generated sectional lift of ``examples/compare/case_data.py``. The
prototype's own ``liftmap`` draws every frame from per-step ``step_<N>.npz`` files
(``lift``: one value per strip, the strips spread evenly over the 12 diameter span),
written here from the same formulas, at the steps of its ``DT`` (0.05). Frame
``FRAME`` of ``FRAMES`` becomes ``golden.png``.

Only the inputs are given here: the case names, colours and labels it takes from
``film_text.toml`` (the same as in ``liftmap.yml``). Lato is the copy bundled with
FlowReel, registered with matplotlib first.

Not part of the package. Run it again only to change the golden frame on purpose.
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
FRAMES, FRAME = 33, 20          # t = 5: the map filled to five eighths
TEXT = {"cases": {"bare": {"name": "Bare", "colour": "#e8b04a"},
                  "helical": {"name": "Helical", "colour": "#6ac1c8"}},
        "plots": {"span": "Span $x/D$", "time": "$tU/D$", "sectional_lift": "Sectional $C_L$"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "liftmap")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "examples" / "compare"))
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import numpy as np

    import case_data
    import render_extras as rx

    from flowreel.compose.style import register_fonts
    register_fonts()
    rx.load_text = lambda: TEXT
    t = case_data.times()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for case in ("bare", "helical"):
            folder = tmp / case
            folder.mkdir()
            lift = case_data.sectional_lift(case, t)
            for ti, row in zip(t, lift):
                np.savez(folder / f"step_{round(ti / rx.DT)}.npz", lift=row)
        rx.liftmap(SimpleNamespace(data=str(tmp / "bare"), data2=str(tmp / "helical"),
                                   out=str(tmp / "frames"), frames=FRAMES))
        args.out.mkdir(parents=True, exist_ok=True)
        shutil.copy(tmp / "frames" / f"frame_{FRAME:05d}.png", args.out / "golden.png")
    print(f"{args.out / 'golden.png'}: frame {FRAME} of {FRAMES}")


if __name__ == "__main__":
    main()
