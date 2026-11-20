# Building the film

Phase 4, branch 5. `film.build` turns a [film file](film.md) into `film.mp4`: every
shot's [finished clip](clips.md), joined in order, with the film's sound under it.

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
| `folder` | `clips/` beside the film file | where clips are kept |
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
