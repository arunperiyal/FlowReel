"""Build the comparison: the two wakes stacked on the left, live plots on the right.

Usage: python compose_compare.py TOP_DIR BOTTOM_DIR OUT_DIR [--across]

This stacks the wakes, one frame per PLT, with the plot area left black; with --across
the two are set side by side instead (left, right), for frames 960 wide. The flow frames
are interpolated to 24 fps when the film is built, and make_film.py then lays plots on
top that are drawn here for every 24 fps frame (plot_frames), so that the moving dots
are sharp rather than smeared by the interpolation.

The plots show mid-span displacement, lift and drag of both cases from series/*_series.csv
(made by extract_series.py), drawn up to the time of each frame. Case names, colours
and axis labels come from film_text.toml; the case labels on the wakes are captions,
added when the film is built.
"""
import argparse
import io
import tomllib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
SIZE = (1920, 1080)
PLOT_WIDTH = 640  # the wakes fill the rest, 1280 x 540 each
GRID = "#3a4046"
AXIS = "#b4bec8"


def load_series(case):
    data = np.loadtxt(ROOT / "series" / f"{case}_series.csv", delimiter=",", skiprows=1)
    return dict(t=data[:, 0], displacement=data[:, 1], lift=data[:, 2], drag=data[:, 3])


def plot_figure(text, series, t_range):
    """The figure, its lines and current-time dots, ready to move along in time."""
    plt.rcParams.update({"font.family": ["Lato", "DejaVu Sans"], "font.size": 17,
                         "mathtext.fontset": "dejavusans", "axes.edgecolor": GRID,
                         "axes.labelcolor": AXIS, "xtick.color": AXIS, "ytick.color": AXIS})
    fig, axes = plt.subplots(3, 1, figsize=(PLOT_WIDTH / 100, SIZE[1] / 100), dpi=100, sharex=True)
    fig.patch.set_facecolor("black")
    fig.subplots_adjust(left=0.2, right=0.95, top=0.93, bottom=0.08, hspace=0.18)
    lines, dots = [], []
    for ax, key in zip(axes, ("displacement", "lift", "drag")):
        ax.set_facecolor("black")
        ax.set_ylabel(text["plots"][key])
        ax.grid(color=GRID, linewidth=0.8)
        ax.tick_params(length=0)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)
        values = np.concatenate([s[key] for s in series.values()])
        low, high = values.min(), values.max()
        pad = 0.12 * (high - low)
        ax.set_ylim(low - pad, high + pad)
        for case, data in series.items():
            colour = text["cases"][case]["colour"]
            (line,) = ax.plot([], [], color=colour, linewidth=2.2,
                              label=text["cases"][case]["name"])
            (dot,) = ax.plot([], [], "o", color=colour, markersize=8)
            lines.append((line, data, key))
            dots.append((dot, data, key))
    axes[-1].set_xlabel(text["plots"]["time"])
    axes[-1].set_xlim(*t_range)
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2, frameon=False,
                   labelcolor="linecolor", handlelength=1.2, fontsize=17)
    return fig, lines, dots


def draw_plots(fig, lines, dots, time):
    """The plots at any time, between samples too: lines end exactly at the dots."""
    for line, data, key in lines:
        shown = data["t"] < time
        value = np.interp(time, data["t"], data[key])
        line.set_data(np.r_[data["t"][shown], time], np.r_[data[key][shown], value])
    for dot, data, key in dots:
        dot.set_data([time], [np.interp(time, data["t"], data[key])])
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor="black")
    return Image.open(buffer).convert("RGB")


def load_text():
    with open(ROOT / "film_text.toml", "rb") as f:
        return tomllib.load(f)


def _plot_chunk(job):
    times, paths, t_range = job
    series = {case: load_series(case) for case in ("bare", "helical")}
    fig, lines, dots = plot_figure(load_text(), series, t_range)
    for time, path in zip(times, paths):
        draw_plots(fig, lines, dots, time).save(path)


def plot_frames(times, out, t_range, jobs=8):
    """One plot image, PLOT_WIDTH x 1080, for each time, as out/plot_00000.png on."""
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"plot_{i:05d}.png" for i in range(len(times))]
    chunks = [(times[k::jobs], paths[k::jobs], t_range) for k in range(jobs)]
    with ProcessPoolExecutor(jobs) as pool:
        list(pool.map(_plot_chunk, chunks))
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("top", type=Path)
    parser.add_argument("bottom", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--across", action="store_true", help="side by side, not stacked")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    tops = sorted(args.top.glob("frame_*.png"))
    for path in tops:
        other = args.bottom / path.name
        if not other.exists():  # stacked frames must show the same step
            continue
        frame = Image.new("RGB", SIZE, "black")
        frame.paste(Image.open(path).convert("RGB"), (0, 0))
        second = (SIZE[0] // 2, 0) if args.across else (0, SIZE[1] // 2)
        frame.paste(Image.open(other).convert("RGB"), second)
        frame.save(args.out / path.name)
    print(f"{args.out}: {len(tops)} frames")


if __name__ == "__main__":
    main()
