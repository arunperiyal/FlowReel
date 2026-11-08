"""Render every shot, then build the film.

Usage: python make_film.py render [--cases DIR] [--bare-jobs N] [--helical-jobs N]
                                  [--frozen-jobs N] [--only NAME ...]   Draw all frames
       python make_film.py film                                         Build film.mp4

All text, its timing and place, and the freezes are in film_text.toml. The order and
length of shots are in SHOTS below.

Interpolated clips are kept in clips/base_*, named by their frames, the frames' times and
the freezes, so changing text or a fade takes about a minute; redrawn frames are noticed.

The live plots of the comparison are drawn here, one per 24 fps frame, and laid over the
interpolated wakes, so changing their labels or colours needs no render.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import matplotlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from compose_compare import PLOT_WIDTH, plot_frames

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent
CASES = ROOT.parent.parent / "cases" / "one_directional_cf"  # change with --cases
BARE = "bare/BR0SG0U1P0"
HELICAL = "helical_grooved/CH4SG3U1P1"
FRAMES = ROOT / "frames"
SURFACE = ROOT / "surface"  # wall shear and sectional forces, from surface_data.py
CLIPS = ROOT / "clips"
OUTPUT = ROOT / "film.mp4"
TEXT_FILE = ROOT / "film_text.toml"
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

T1, T2 = 5000, 5600  # the same window for both cases
EXTRA_T2 = 5240  # the explaining shots after the comparison use the first 6 s only
STEP = 5  # solver steps between flow frames
DT = 0.05  # time per solver step, in D/U
# Frames drawn at once. Each job uses about one core; memory sets the limit:
# about 0.7 GB per bare job and 2.2 GB per helical job. These suit the workstation
# (31 GB); render_airavata.slurm passes larger numbers.
JOBS = dict(bare=24, helical=12, frozen=12)
REVEAL = (48, 72)  # frames over which the cutting plane sweeps, at 8 fps
FPS = 24
FLOW_FPS = 8  # one PLT per video frame, before interpolation
SIZE = (1920, 1080)
SMOOTH = f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1:scd=none"

LOGO = ROOT / "assets" / "iitkgp_logo_white.png"
LOGO_HEIGHT = 190
FONT, FONT_LIGHT = "Lato-Regular.ttf", "Lato-Light.ttf"
WHITE = "#f2f2f2"
MUTED = "#96a5b2"
CAPTION_MARGIN = 80  # from the top or bottom edge, for "top" and "bottom"
CAPTION_FADE = 0.8

# Each shot: frames at fps, a still card, or the last frame of another shot held.
# fade is (in, out) in seconds; fade_out_at starts the fade out early.
SHOTS = [
    dict(name="opening", card="opening", fade=(1.5, 1.5)),
    dict(name="domain", frames="bare_domain", fps=FPS, fade=(1.5, 0)),
    dict(name="bare_reveal", frames="bare_reveal", fps=FLOW_FPS, fade=(0, 1)),
    # Grooves are cut into the smooth cylinder; it ends on the main view, and the
    # helical wake reveal fades in over it.
    dict(name="carve", frames="carve", fps=FPS, fade=(1, 1)),
    dict(name="helical_reveal", frames="helical_reveal", fps=FLOW_FPS, fade=(1, 1)),
    dict(name="compare", frames="compare", fps=FLOW_FPS, fade=(1, 1), plots=True),
    # Why the grooves work: the wake along the span from above and in cuts, the flow at a
    # groove, where the flow leaves the wall, and the lift along the span.
    dict(name="top", frames="top", fps=FLOW_FPS, fade=(1, 1)),
    dict(name="slices", frames="slices", fps=FLOW_FPS, fade=(1, 1)),
    # Streamlines are redrawn every frame, so interpolation smears them: repeat frames.
    dict(name="section", frames="helical_section", fps=FLOW_FPS, fade=(1, 1), smooth=False),
    dict(name="wall", frames="wall", fps=FLOW_FPS, fade=(1, 1)),
    dict(name="liftmap", frames="liftmap", fps=FPS, fade=(1, 0)),
    # The last frame fades out; a closing line can then sit on black.
    dict(name="end", hold="liftmap", seconds=13, fade=(0, 2), fade_out_at=0.5),
]


def run(command):
    subprocess.run([str(part) for part in command], check=True)


def load_text():
    with open(TEXT_FILE, "rb") as f:
        return tomllib.load(f)


def render_commands(cases, jobs):
    python = sys.executable
    flow = [ROOT / "render_frames.py"]
    frozen = ROOT / "render_frozen.py"
    extras = ROOT / "render_extras.py"
    stack = ROOT / "compose_compare.py"
    short = ["--t1", T1, "--t2", EXTRA_T2]
    bare, helical = cases / BARE, cases / HELICAL
    window = ["--t1", T1, "--t2", T2]
    reveal = ["--look", "reveal", "--reveal-start", REVEAL[0], "--reveal-end", REVEAL[1]]
    on = {key: ["--jobs", value] for key, value in jobs.items()}
    still = ["--time-step", T1, *on["frozen"]]
    return {
        "domain": [python, frozen, "domain", bare, FRAMES / "bare_domain", *still],
        "carve": [python, ROOT / "render_carve.py", FRAMES / "carve", *on["frozen"]],
        "bare_reveal": [python, *flow, bare, FRAMES / "bare_reveal", *window, *reveal, *on["bare"]],
        "helical_reveal": [python, *flow, helical, FRAMES / "helical_reveal", *window, *reveal,
                           *on["helical"]],
        "bare_panel": [python, *flow, bare, FRAMES / "bare_panel", *window, "--view", "panel",
                       *on["bare"]],
        "helical_panel": [python, *flow, helical, FRAMES / "helical_panel", *window, "--view",
                          "panel", *on["helical"]],
        "compare": [python, stack, FRAMES / "bare_panel", FRAMES / "helical_panel",
                    FRAMES / "compare"],
        "bare_top": [python, *flow, bare, FRAMES / "bare_top", *short, "--view", "top",
                     *on["bare"]],
        "helical_top": [python, *flow, helical, FRAMES / "helical_top", *short, "--view", "top",
                        *on["helical"]],
        "top": [python, stack, FRAMES / "bare_top", FRAMES / "helical_top", FRAMES / "top",
                "--across"],
        "section": [python, extras, "section", helical, FRAMES / "helical_section", *short,
                    *on["helical"]],
        "bare_slices": [python, extras, "spanslices", bare, FRAMES / "bare_slices", *short,
                        *on["bare"]],
        "helical_slices": [python, extras, "spanslices", helical, FRAMES / "helical_slices",
                           *short, *on["helical"]],
        "slices": [python, stack, FRAMES / "bare_slices", FRAMES / "helical_slices",
                   FRAMES / "slices"],
        "bare_surface_data": [python, ROOT / "surface_data.py", bare, SURFACE / "bare", *window,
                              *on["bare"]],
        "helical_surface_data": [python, ROOT / "surface_data.py", helical, SURFACE / "helical",
                                 *window, *on["helical"]],
        "bare_wall": [python, extras, "wall", SURFACE / "bare", FRAMES / "bare_wall", *short,
                      *on["frozen"]],
        "helical_wall": [python, extras, "wall", SURFACE / "helical", FRAMES / "helical_wall",
                         *short, *on["frozen"]],
        "wall": [python, stack, FRAMES / "bare_wall", FRAMES / "helical_wall", FRAMES / "wall"],
        "liftmap": [python, extras, "liftmap", SURFACE / "bare", SURFACE / "helical",
                    FRAMES / "liftmap"],
    }


def centred(draw, y, text, font, fill):
    width = draw.textlength(text, font=font)
    draw.text(((SIZE[0] - width) / 2, y), text, font=font, fill=fill)


def opening_card(path, text):
    """Logo, title and credits in one scene."""
    card = Image.new("RGB", SIZE, "black")
    draw = ImageDraw.Draw(card)
    logo = Image.open(LOGO).convert("RGBA")
    logo = logo.resize((round(logo.width * LOGO_HEIGHT / logo.height), LOGO_HEIGHT), Image.LANCZOS)
    card.paste(logo, ((SIZE[0] - logo.width) // 2, 110), logo)
    title = ImageFont.truetype(FONT, 60)
    for i, line in enumerate(text["title"]):
        centred(draw, 370 + 82 * i, line, title, WHITE)
    draw.line((SIZE[0] / 2 - 160, 572, SIZE[0] / 2 + 160, 572), fill=MUTED, width=2)
    small, large = ImageFont.truetype(FONT, 28), ImageFont.truetype(FONT_LIGHT, 42)
    y = 620
    for heading, names in (("CREATED BY", text["created_by"]), ("CO-AUTHORED BY", text["coauthors"])):
        centred(draw, y, heading, small, MUTED)
        y += 44
        for name in names:
            centred(draw, y, name, large, WHITE)
            y += 58
        y += 26
    card.save(path)


def text_layer(lines, size, colour, place, centre):
    """The lines drawn on a transparent frame, with any $...$ set as mathematics in Lato.
    Returns the layer and the text's box (left, top, right, bottom) in pixels."""
    matplotlib.rcParams.update({"mathtext.fontset": "custom", "mathtext.rm": "Lato",
                                "mathtext.it": "Lato:italic", "mathtext.bf": "Lato:bold"})
    fig = plt.figure(figsize=(SIZE[0] / 100, SIZE[1] / 100), dpi=100)
    fig.patch.set_alpha(0)
    points = size * 72 / 100  # letter height in pixels to font size in points
    spacing = round(size * 1.3)
    texts = [fig.text(0, 1, line, fontsize=points, color=colour, family="Lato", va="top")
             for line in lines]
    renderer = fig.canvas.get_renderer()
    widths = [t.get_window_extent(renderer).width for t in texts]
    height = spacing * len(lines)
    if isinstance(place, list):
        left, top = place
        if left == "centre":  # ["centre", y]: centred across the frame, top at y
            left = (SIZE[0] - max(widths)) / 2
    else:
        left = (SIZE[0] - max(widths)) / 2
        top = {"top": CAPTION_MARGIN, "centre": (SIZE[1] - height) / 2,
               "bottom": SIZE[1] - CAPTION_MARGIN - height}[place]
    for i, (t, width) in enumerate(zip(texts, widths)):
        x = left + (max(widths) - width) / 2 if centre else left
        t.set_position((x / SIZE[0], 1 - (top + i * spacing) / SIZE[1]))
    fig.canvas.draw()
    layer = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy())
    plt.close(fig)
    return layer, (left, top, left + max(widths), top + height)


def draw_arrow(draw, start, end, colour, width):
    """A straight arrow with a filled head at end."""
    start, end = complex(*start), complex(*end)
    along = (end - start) / abs(end - start)
    head = 4.5 * width
    base = end - head * along
    side = along * 1j * head * 0.5
    draw.line([(start.real, start.imag), (base.real, base.imag)], fill=colour, width=width)
    draw.polygon([(end.real, end.imag), ((base + side).real, (base + side).imag),
                  ((base - side).real, (base - side).imag)], fill=colour)


def caption_image(caption, path):
    """One caption on a transparent frame, with a soft shadow or a dark box behind it,
    and any arrows, given as [x1, y1, x2, y2] in pixels, pointing to x2, y2."""
    size = caption.get("size", 50)
    colour = caption.get("colour", WHITE)
    text, (left, top, right, bottom) = text_layer(
        caption["lines"], size, colour, caption.get("place", "bottom"),
        caption.get("align", "centre") == "centre")
    draw = ImageDraw.Draw(text)
    for x1, y1, x2, y2 in caption.get("arrows", []):
        draw_arrow(draw, (x1, y1), (x2, y2), colour, caption.get("arrow_width", 4))
    back = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    if caption.get("box"):
        pad = round(size * 0.6)
        ImageDraw.Draw(back).rounded_rectangle(
            (left - pad, top - pad * 0.7, right + pad, bottom + pad * 0.3),
            radius=12, fill=(0, 0, 0, 175))
    else:
        back.putalpha(text.getchannel("A").filter(ImageFilter.MaxFilter(9))
                      .filter(ImageFilter.GaussianBlur(12)))
    Image.alpha_composite(back, text).save(path)


ENCODE = ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", FPS, "-colorspace", "bt709",
          "-color_primaries", "bt709", "-color_trc", "bt709", "-video_track_timescale", "24000"]
TO_709 = "scale=out_color_matrix=bt709:out_range=tv"


def frame_files(shot):
    return sorted((FRAMES / shot["frames"]).glob("frame_*.png"))


def freezes(shot, text):
    """The shot's freezes in order, each with its start in the finished shot."""
    found = sorted((f for f in text.get("freeze", []) if f["shot"] == shot["name"]),
                   key=lambda f: f["at"])
    shift = 0.0
    for freeze in found:
        freeze["starts"] = freeze["at"] + shift
        shift += freeze["hold"]
    return found


def duration(shot, text):
    if "card" in shot:
        return text[shot["card"]]["seconds"]
    if "seconds" in shot:
        return shot["seconds"]
    return len(frame_files(shot)) / shot["fps"] + sum(f["hold"] for f in freezes(shot, text))


def frame_sequence(shot, text):
    """Frame files in playing order, with frozen frames repeated for their hold."""
    files = frame_files(shot)
    order, done = [], 0
    for freeze in freezes(shot, text):
        stop = min(round(freeze["at"] * shot["fps"]), len(files) - 1)
        order += files[done:stop + 1] + [files[stop]] * round(freeze["hold"] * shot["fps"])
        done = stop + 1
    return order + files[done:]


T_RANGE = (T1 * DT, T2 * DT)


def plot_settings(text):
    return json.dumps([text["plots"], text["cases"]], sort_keys=True)


def plots_for(shot, order, text):
    """Plot images for every 24 fps frame of a flow shot, in a folder kept between builds.

    Output frame j lies a third of the way from one flow frame to the next, so its time
    is taken between theirs; during a freeze both are the same frame and time stops.
    """
    index = {path: i for i, path in enumerate(frame_files(shot))}
    flow = [index[path] for path in order]
    ratio = FPS // shot["fps"]
    times = []
    for j in range(len(flow) * ratio):
        k, part = divmod(j, ratio)
        a, b = flow[k], flow[min(k + 1, len(flow) - 1)]
        times.append((T1 + STEP * (a + (b - a) * part / ratio)) * DT)
    key = hashlib.sha1((json.dumps([round(t, 6) for t in times]) + plot_settings(text))
                       .encode()).hexdigest()[:8]
    folder = CLIPS / f"plots_{shot['name']}"
    stamp = folder / "key.txt"
    if not stamp.exists() or stamp.read_text() != key:
        for old in folder.glob("plot_*.png"):
            old.unlink()
        plot_frames(times, folder, T_RANGE)
        stamp.write_text(key)
    return folder, key


def final_frame(name, text):
    """The last frame of a shot, with its plots when it has them, and a key for it."""
    shot = next(s for s in SHOTS if s["name"] == name)
    last = frame_files(shot)[-1]
    drawn = f"{last}{last.stat().st_mtime_ns}"  # a redrawn frame gives a new key
    if not shot.get("plots"):
        return last, drawn
    path = CLIPS / f"final_{name}.png"
    plot = plot_frames([T_RANGE[1]], CLIPS / f"plots_final_{name}", T_RANGE, jobs=1)[0]
    frame = Image.open(last).convert("RGB")
    frame.paste(Image.open(plot).convert("RGB"), (SIZE[0] - PLOT_WIDTH, 0))
    frame.save(path)
    return path, f"{drawn}{plot_settings(text)}"


def base_clip(shot, text):
    """The shot before fades and captions; only flow shots take long."""
    if "card" in shot:
        still = CLIPS / f"card_{shot['name']}.png"
        opening_card(still, text[shot["card"]])
        source = ["-loop", 1, "-t", duration(shot, text), "-i", still]
        chain, key = TO_709, json.dumps(text[shot["card"]], sort_keys=True)
    elif "hold" in shot:
        last, key = final_frame(shot["hold"], text)
        source = ["-loop", 1, "-t", shot["seconds"], "-i", last]
        chain, key = TO_709, f"{key}{shot['seconds']}"
    else:
        order = frame_sequence(shot, text)
        sequence = CLIPS / f"sequence_{shot['name']}"
        sequence.mkdir(parents=True, exist_ok=True)
        for old in sequence.glob("*.png"):
            old.unlink()
        for i, file in enumerate(order):
            (sequence / f"frame_{i:05d}.png").symlink_to(file)
        source = ["-framerate", shot["fps"], "-i", sequence / "frame_%05d.png"]
        if shot["fps"] == FPS:
            chain = TO_709
        elif shot.get("smooth", True):
            chain = f"{SMOOTH},{TO_709}"
        else:
            chain = f"fps={FPS},{TO_709}"
        key = json.dumps([(p.name, p.stat().st_mtime_ns) for p in order])  # redrawn: new key
        if shot.get("plots"):
            # Only the wakes are interpolated; sharp plots go on top at 24 fps.
            folder, plots_key = plots_for(shot, order, text)
            source += ["-framerate", FPS, "-i", folder / "plot_%05d.png"]
            chain = (f"[0:v]{SMOOTH}[w];[w][1:v]overlay={SIZE[0] - PLOT_WIDTH}:0"
                     f":eof_action=repeat,{TO_709}")
            key += plots_key
    digest = hashlib.sha1((key + chain).encode()).hexdigest()[:8]  # a new filter: a new clip
    path = CLIPS / f"base_{shot['name']}_{digest}.mp4"
    if not path.exists():
        for old in CLIPS.glob(f"base_{shot['name']}_*.mp4"):
            old.unlink()
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *source, "-filter_complex",
             chain, *ENCODE, "-crf", 10, "-preset", "medium", path])
    return path


def shot_captions(shot, text, length):
    """Captions and freeze text of one shot, with start and end in the finished shot."""
    found = []
    for caption in text.get("caption", []):
        if caption["shot"] == shot["name"]:
            found.append(dict(caption, end=caption.get("end", length)))
    for freeze in freezes(shot, text):
        if freeze.get("lines"):
            found.append(dict(freeze, start=freeze["starts"] + 0.3,
                              end=freeze["starts"] + freeze["hold"] - 0.2))
    return found


def finished_clip(shot, text):
    base = base_clip(shot, text)
    path = CLIPS / f"shot_{shot['name']}.mp4"
    length = duration(shot, text)
    fade_in, fade_out = shot.get("fade", (0, 0))
    # Fades act on the picture before captions go on, so a caption can sit on black.
    chain = []
    if fade_in:
        chain.append(f"fade=in:st=0:d={fade_in}")
    if fade_out:
        chain.append(f"fade=out:st={shot.get('fade_out_at', length - fade_out)}:d={fade_out}")
    filters, inputs, last = [f"[0:v]{','.join(chain) or 'null'}[v]"], ["-i", base], "v"
    for i, caption in enumerate(shot_captions(shot, text, length)):
        image = CLIPS / f"caption_{shot['name']}_{i}.png"
        caption_image(caption, image)
        start, end = caption["start"], min(caption["end"], length)
        inputs += ["-loop", 1, "-t", end + 1, "-i", image]
        fades = f"fade=in:st={start}:d={CAPTION_FADE}:alpha=1," if start > 0 else ""
        if end < length:
            fades += f"fade=out:st={end - CAPTION_FADE}:d={CAPTION_FADE}:alpha=1,"
        filters.append(f"[{i + 1}:v]format=rgba,{fades}null[c{i}]")
        filters.append(f"[{last}][c{i}]overlay=eof_action=pass[v{i}]")
        last = f"v{i}"
    filters.append(f"[{last}]null[out]")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex",
         ";".join(filters), "-map", "[out]", "-t", length, *ENCODE, "-crf", 14, "-preset", "slow",
         path])
    return path


def media_length(path):
    """Seconds in a video or audio file, as measured, not as planned."""
    probe = str(FFMPEG).replace("ffmpeg", "ffprobe")
    found = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(path)],
                           check=True, capture_output=True, text=True)
    return float(found.stdout.strip())


def add_audio(picture, audio):
    """The film with the [audio] track under it: trimmed from start, at volume, faded in
    and out, and cut to the picture's measured length. The fade ends with the last frame,
    or with the track if that is shorter. The picture is copied, not re-encoded."""
    track = ROOT / audio["file"]
    length = media_length(picture)
    ends = min(length, media_length(track) - audio.get("start", 0))
    fade_out = audio.get("fade_out", 3)
    chain = (f"atrim=start={audio.get('start', 0)},asetpts=PTS-STARTPTS,"
             f"volume={audio.get('volume', 1.0)},"
             f"afade=t=in:d={audio.get('fade_in', 1)},"
             f"afade=t=out:st={ends - fade_out}:d={fade_out}")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", picture, "-i", track,
         "-map", "0:v", "-map", "1:a", "-af", chain, "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-t", length, "-movflags", "+faststart", OUTPUT])


def build_film():
    CLIPS.mkdir(exist_ok=True)
    text = load_text()
    clips = [finished_clip(shot, text) for shot in SHOTS]
    listing = CLIPS / "film_list.txt"
    listing.write_text("".join(f"file '{clip}'\n" for clip in clips))
    length = sum(duration(shot, text) for shot in SHOTS)
    picture = CLIPS / "film_picture.mp4" if "audio" in text else OUTPUT
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", 0,
         "-i", listing, "-c", "copy", "-movflags", "+faststart", picture])
    if "audio" in text:
        add_audio(picture, text["audio"])
    for shot in SHOTS:
        print(f"  {shot['name']:16s} {duration(shot, text):5.1f} s")
    print(f"{OUTPUT}: {length:.1f} s" + (f", with {text['audio']['file']}" if "audio" in text else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["render", "film"])
    parser.add_argument("--cases", type=Path, default=CASES,
                        help=f"folder holding {BARE} and {HELICAL}")
    for key, value in JOBS.items():
        parser.add_argument(f"--{key}-jobs", type=int, default=value)
    parser.add_argument("--only", nargs="+", help="render only these named stages")
    args = parser.parse_args()
    if args.action == "film":
        build_film()
        return
    jobs = {key: getattr(args, f"{key}_jobs") for key in JOBS}
    commands = render_commands(args.cases.resolve(), jobs)
    for name in args.only or commands:
        print(f"== {name}", flush=True)
        run(commands[name])


if __name__ == "__main__":
    main()
