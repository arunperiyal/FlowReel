"""Draw the golden comparison frame with the prototype's ``compose_compare.py``.

Usage: python tools/make_compare_golden.py [--out tests/data/compare]

The data are the generated cases of ``examples/compare/case_data.py``. The prototype's
own code draws the frame, as the AFMS film did:

- ``compose_compare.main`` stacks the two wake frames (bare on top, helical below);
- ``compose_compare.plot_figure`` and ``draw_plots`` draw the live plots at the frame's
  time, from the cases' series CSV (the prototype's format, read by its own
  ``load_series``);
- the plots are laid on the right as ``make_film.py`` does (``frame.paste(plot,
  (SIZE[0] - PLOT_WIDTH, 0))``).

Only the inputs are the prototype's to read: its ``ROOT`` is pointed at a folder
holding the generated ``series/``, and the case names, colours and axis labels it
takes from ``film_text.toml`` are given here, the same as in ``plots.yml``. Lato is the
copy bundled with FlowReel, registered with matplotlib first.

Not part of the package. Run it again only to change the golden frame on purpose.
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAME = 15                     # t = 5.77, between two samples of the series
TEXT = {"cases": {"bare": {"name": "Bare", "colour": "#e8b04a"},
                  "helical": {"name": "Helical", "colour": "#6ac1c8"}},
        "plots": {"displacement": "Mid-span $y/D$", "lift": "$C_L$", "drag": "$C_D$",
                  "time": "$tU/D$"}}
T_RANGE = (0.0, 8.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "tests" / "data" / "compare")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "examples" / "compare"))
    sys.path.insert(0, str(ROOT / "prototype" / "afms"))
    import case_data
    import compose_compare as cc
    from PIL import Image

    from flowreel.compose.style import register_fonts
    register_fonts()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        case_data.write_data(tmp)
        (tmp / "series").mkdir()
        for case in ("bare", "helical"):
            shutil.copy(tmp / "data" / f"{case}_series.csv", tmp / "series")
        cc.ROOT = tmp
        sys.argv = ["compose_compare.py", str(tmp / "frames" / "bare_wake"),
                    str(tmp / "frames" / "helical_wake"), str(tmp / "stacked")]
        cc.main()
        series = {case: cc.load_series(case) for case in ("bare", "helical")}
        fig, lines, dots = cc.plot_figure(TEXT, series, T_RANGE)
        plot = cc.draw_plots(fig, lines, dots, case_data.WAKE_TIMES[FRAME])
        frame = Image.open(tmp / "stacked" / f"frame_{FRAME:05d}.png").convert("RGB")
        frame.paste(plot, (cc.SIZE[0] - cc.PLOT_WIDTH, 0))    # as make_film.py lays them
        args.out.mkdir(parents=True, exist_ok=True)
        frame.save(args.out / "golden.png", optimize=True)
    print(f"{args.out / 'golden.png'}: frame {FRAME}, t = {case_data.WAKE_TIMES[FRAME]}")


if __name__ == "__main__":
    main()
