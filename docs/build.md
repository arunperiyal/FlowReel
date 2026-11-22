# Building the film

`film.build` turns a [film file](film.md) into `film.mp4`: every
shot's [finished clip](clips.md), joined in order, with the film's sound under it.
From the command line it is `flowreel film build`, and the checks below are `film
check`, `film lengths`, `film srt` and `film chapters` ([commands](commands.md#film-build)).

```python
from flowreel.film.build import build

built = build("film.yml", preview=480)
print("\n".join(built.table()))
```

```text
shot     planned  measured
opening    2.00 s    2.00 s  kept
wake       4.50 s    4.50 s  built
end        2.00 s    2.00 s  kept
film       8.50 s    8.50 s  film.mp4
preview film_480p.mp4
```

| Argument | Default | Meaning |
|---|---|---|
| `folder` | `clips/` at the project root (beside the film file outside a project) | where clips are kept |
| `force` | `False` | rebuild every clip, ignoring keys |
| `mute` | `False` | leave the sound out |
| `preview` | none | height in pixels of a preview copy to write too |
| `crf` | `28` | the preview's quality (lower is better and larger) |
| `panels` | `{}` | options for drawing a layout's live panels, such as `jobs` |

## The join

The finished clips are joined by ffmpeg's `concat` demuxer with the picture copied, not
encoded again. That works because every clip is encoded alike (H.264, yuv420p, the
film's rate and time base), and it is why joining an hour's film takes seconds. A build
redoes only clips whose key changed, so after a caption edit the build costs one
finished clip and the join.

Each shot's **planned** length comes from [the timeline](film.md#the-timeline-filmtimeline),
its **measured** length from its clip with `ffprobe`. The two should agree to a
millisecond; a shot that differs shows at once in the report. The film's measured
length is the sum of its clips', and the sound is cut to it.

## Sound

The film's `audio` tracks ([keys](film.md#audio)) are trimmed, faded and mixed under the
joined picture in the same ffmpeg run, and encoded as AAC at 192 kb/s. A track's fade
out ends where it stops: at the picture's end or where the file runs out, whichever is
first. Each track gets a line in the report:

```text
audio music.mp3: 0.00 to 8.50 s of the film (file 182.40 s)
```

## Preview copy

`preview: 480` writes `film_480p.mp4` beside the film, for sending to someone: 480
pixels high, the width from the film's aspect ratio, encoded once at `crf` 28. It is
the built film scaled, so no frame or caption is drawn again; the text was laid out in
the film's pixels and shrinks with the picture. It keeps the sound and the chapters.
The height must be even (H.264 in yuv420p needs it) and no taller than the film, and is
checked before any clip is built.

## One shot

`only: compare` builds that shot's finished clip alone and copies it to
`film_compare.mp4` beside the film, without sound, to check its captions without
building or joining the rest. The whole film is still laid out, since a caption can run
across a cut. The clip is the one the full build will use, so it is kept for it.

## Subtitles: `film.srt`

A whole build also writes the captions as SubRip subtitles, `film.srt` beside the film
(when there are captions), with their film times from the timeline: for a player's
subtitle track, a transcript, or a site that takes captions. One block per caption, its
lines kept. Subtitles have no maths font, so `$...$` becomes plain text: `$U = 1$` is
`U = 1`, `\times` is `×`, `\alpha` and `\Delta` are `α` and `Δ`, `\mathrm{Re}` is
`Re`; sub- and superscripts stay as written (`C_D`). `film.check.srt(timeline)` writes
it without building.

## Contact sheet: `contact.png`

`film.check.contact` draws stills of the finished film on one picture, `contact.png`
beside the film, to check the words and their places without playing the film. Each
still is labelled with its film time, its shot and why it was taken; the captions are
drawn in place, as they show.

```python
from flowreel.film.check import contact

contact("film.yml", at="caption")          # or "freeze", or "every:5"
```

| `at` | A still |
|---|---|
| `caption` (default) | at the middle of each caption, when it is fully faded in |
| `freeze` | at the middle of each freeze |
| `every:S` | every `S` seconds from the start |

`columns` (default 4) and `width` (pixels of a still, default 480, at most the film's)
set the sheet's layout. The stills come from the finished clips, built when missing, so
no join is needed.

![A contact sheet every 0.25 s of a small film: the freeze holds one frame, the caption
runs across the cut](images/contact.png)

## Chapters

Chapters let a viewer jump between the parts of a long film, as between the slides of
an hour's talk. A shot starts one with `chapter:`; it runs until the next chapter, or
the film's end.

```yaml
shots:
  - {name: opening, card: cards/opening.yml, seconds: 7, chapter: Opening}
  - {name: domain, frames: frames/bare_domain, chapter: The set-up}
  - {name: bare_reveal, frames: frames/bare_reveal}          # still "The set-up"
  - name: compare
    layout: compare.yml
    chapter: {title: Smooth against grooved, at: 2.5}        # 2.5 s into the shot
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `chapter` | text, or `{title, at}` | none | a one-line title |
| `chapter.at` | seconds | `0` | where in the finished shot (freezes included) it starts; must be inside the shot |

Times come from the timeline (`timeline(f).chapters`), so moving or adding shots moves
the chapters with them.

**In the film.** The build hands ffmpeg a metadata file of the chapters at the join
(`-map_chapters`), so they cost no encoding; changing a title rebuilds no clip. The
preview copy keeps them. Desktop players (VLC, mpv, IINA, QuickTime) show a chapter
menu and next and previous keys; mp4 stores them twice, as a chapter list and as a
QuickTime chapter track, which `ffprobe` lists as a `data` stream. YouTube, browsers and,
as far as known, video in PowerPoint ignore them.

**For YouTube: `chapters.txt`.** YouTube reads chapters from timestamps in a video's
description, so the build writes them beside the film, ready to paste:

```text
0:00 Opening
0:07 The set-up
1:12 Smooth against grooved
```

Times are whole seconds, rounded down so a chapter never starts late. YouTube shows
chapters only when the first is at `0:00`, there are at least three, and each lasts at
least ten seconds; the build's report notes any of these a film misses, without
stopping (a talk's film may never go there).

**Not a pause.** A player does not stop at a chapter's end. For a talk, end a chapter on
a hold (`hold_last_of`) or a freeze, and pause the player there.

## Example

`examples/film_build/run.py` builds a small film from generated frames and a generated
440 Hz tone, with no data, logo or music: an opening card, a wake with a freeze and
captions, its last frame held under a closing line, and three chapters. It writes
`film.mp4`, `film_180p.mp4`, `film.srt`, `chapters.txt` and `contact.png` and prints the
report. Run it twice: the second run keeps every clip and only joins again.

```bash
python examples/film_build/run.py /tmp/film_build_example
```

`examples/film_commands/run.sh` does the same with the `film` commands: `film template`,
`film lengths` before and after `film build --preview 180`, `film check`, `film srt` and
`film chapters`.

```bash
sh examples/film_commands/run.sh /tmp/film_commands_example
```

## A film project

`examples/film_project/run.py` builds a silent film from a project folder of generated
data, with what a real film uses: an opening card, the comparison of two cases as a
[layout](layouts.md) whose live plots are a `rate: output` panel, a freeze with its own
text, the last frame held with its plots under a closing line, and a watermark of text.
The cases and their wake frames come from the [comparison example](compose.md)
(`examples/compare/case_data.py`).

```bash
python examples/film_project/run.py /tmp/film_project_example
```

```text
shot     planned  measured
opening    2.00 s    2.00 s  built
compare    4.50 s    4.50 s  built
end        2.00 s    2.00 s  built
film       8.50 s    8.50 s  film.mp4
srt film.srt
```

The wakes are interpolated from 8 to 24 frames a second, but the plots are not: they are
drawn once per output frame (108 here: 24 wake frames and a 1.5 s freeze, three output
frames each) and laid on top, so their dots stay sharp and stop during the freeze.

## The AFMS film

The AFMS film, the film FlowReel was written to rebuild, has its own FlowReel files.
`tools/afms_film.py OUT` writes them from the prototype's `make_film.py` (the shot list)
and `film_text.toml` (every word, the freezes, the card, the music): `film.yml`, a text
file per shot and per freeze, `cards/opening.yml`, and the comparison as a layout
(`compare.yml`) with its live plots (`plots.yml`, from the cases' series in
`flowreel.yml`). The project folder lives with the research data, not in this
repository, since its files name the logo and the licensed track. The prototype's
frame folders, series CSV, logo and track are copied into it under the names it gives.

`tests/test_golden_film.py` writes the files into a temporary folder with generated
frame folders of the film's own counts and checks them against the prototype's own
functions:

| Check | Against |
|---|---|
| each shot's planned length, and the film's (131.875 s) | `make_film.duration` |
| each caption's start and end in its shot, freeze text included | `make_film.shot_captions` |
| all 32 captions drawn, with their shadows, boxes and arrows | `make_film.caption_image`, same limits as the golden frames; a caption moved by 4 by 3 pixels fails |
| the opening card, with a generated logo | `make_film.opening_card` |

The rebuild from the real frames reads the research repository's final copy of the
scripts (`--prototype`), which is newer than `prototype/afms`: it moves some captions
and sets the film in Times New Roman with STIX maths (its `[style]`), which the tool
writes into the film's and the plots' `style`.

```bash
python tools/afms_film.py ~/path/to/afms_project --prototype ~/path/to/studies/afms_video
# then copy or link frames/, series/ and assets/ from afms_video
cd ~/path/to/afms_project
flowreel film build --preview 480
flowreel film check --at caption
```

Its lengths per shot are compared with the prototype's film and its contact sheet with
the prototype's film at the same times; the results are recorded in `docs/PLAN.md`
(Section 19.5).
