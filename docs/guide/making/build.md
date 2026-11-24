# Building the film

`flowreel film build` makes the film from its scenes: a clip per scene, kept by its key,
then the film with its sound, chapters and subtitles.

```text
$ flowreel film build --preview 480
scene    planned  measured
opening    6.00 s    6.00 s  built
reveal    12.00 s   12.00 s  kept
...
```

`flowreel film build` makes a clip per scene, then the film.

## Length

A scene of `seconds` lasts that long; otherwise its main box's frames at its `rate`,
each shown for a whole step, plus its freezes. A shot box's frames are rendered
beforehand. A missing one stops the build, naming the shot and the command that renders
it. Every shot or panel box plays from the scene's start and holds its last frame once
it ends.

## Rates

A shot at the film's rate, or under `to_output: repeat`, shows each frame as it is;
`blend` cross-fades the two frames around a moment; `interpolate` makes the frames
between with ffmpeg's motion interpolation, once, kept under `clips/`. A panel is drawn
at the box's size on every output frame, at the time between two of its frames, so its
dot moves smoothly and is never smeared.

## A clip per scene

Each frame drawn as [layouts](../film/layouts.md#how-a-frame-is-drawn) say, faded from
and to black by the scene's `fade`, with the watermark where it shows. The clip's name
holds a key of everything in it, so a changed caption rebuilds one scene and keeps the
others. A scene that holds another's last frame is rebuilt only when that frame's pixels
change.

## Scenes joined into the film

A scene's `cross` dissolves its last seconds into the next scene's first, so the film is
the scenes' lengths less the crosses. Without a cross the clips are joined without
encoding again. Audio, the preview copy (`--preview`) and `--only SCENE` are below.

## Subtitles and chapters (in short)

Every text box with `at` (and `subtitle` left true) is a subtitle in `film.srt`, from
the scene's start. A scene's `chapter` starts a chapter at the scene's start plus its
`at`. `film lengths` prints each scene's planned length and, when its clip is built and
current, its measured one; `film check` makes the contact sheet, with stills at the
middle of each timed text box (`--at caption`), of each freeze (`--at freeze`) or every
few seconds (`--at every:S`).

## Sound

The film's `audio` tracks ([keys](../film/film.md#audio)) are trimmed, faded and mixed under the
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

## One scene

`film build --only SCENE` builds that scene's clip alone and copies it to
`film_SCENE.mp4` beside the film, without sound, to check it without building or
joining the rest. The clip is the one the full build will use, so it is kept for it.

## Building as you edit: `--watch`

```text
$ flowreel film build --watch --preview 540
shot      planned  measured
...
built in 4.0 s
watching /home/you/films/cylinder for changes (Ctrl-C to stop)
```

`--watch` builds, then builds again each time a file the film may be made from changes:
the film file, a layout file, a frame folder (a shot rendered again), a panel, a picture
or a sound. Only the clips whose inputs changed are made again, so a caption edited is
in the film in seconds. It stops at Ctrl-C.

It does not read the film file to learn what to watch: it looks at every file under the
film file's folder, by size and time of change, once a second. That leaves out what the
build writes (`clips/`, `.flowreel/`, the films and subtitles beside the film file) and
folders reached through a link, such as `data/`. A change starts a build once the files
have stood still for half a second, so a shot still being rendered is not built half
way, and a change made during a build starts another when it ends. A build that fails,
on a film file left half edited, says why and waits for the next change.

`--watch` builds here, never as a Slurm job, and refuses `--force`, which would make
every clip again on every change.

## Subtitles: `film.srt`

A whole build also writes the timed text boxes as SubRip subtitles, `film.srt` beside the film
(when there are any), with their film times: for a player's
subtitle track, a transcript, or a site that takes captions. One block per text box, its
lines kept. Subtitles have no maths font, so `$...$` becomes plain text: `$U = 1$` is
`U = 1`, `\times` is `×`, `\alpha` and `\Delta` are `α` and `Δ`, `\mathrm{Re}` is
`Re`; sub- and superscripts stay as written (`C_D`). `film srt` writes it without building.

## Chapters

Chapters let a viewer jump between the parts of a long film, as between the slides of
an hour's talk. A scene starts one with `chapter:`; it runs until the next chapter, or
the film's end.

```yaml
scenes:
  - {name: opening, seconds: 7, chapter: Opening, layout: opening}
  - {name: domain, chapter: The set-up, layout: {boxes: [{shot: shots/domain.yml}]}}
  - {name: reveal, layout: {boxes: [{shot: shots/reveal.yml}]}}   # still "The set-up"
  - name: compare
    layout: compare
    chapter: {title: Smooth against grooved, at: 2.5}             # 2.5 s into the scene
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `chapter` | text, or `{title, at}` | none | a one-line title |
| `chapter.at` | seconds | `0` | where in the scene (freezes included) it starts |

Times come from the film's plan (`scene_build.plan(film).chapters`), so moving or
adding scenes moves the chapters with them.

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
a held frame (a `last_frame` box) or a freeze, and pause the player there.
