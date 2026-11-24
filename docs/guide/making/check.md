# Checking the film

A film can be checked without watching it: the scenes and their lengths, stills of a
scene before anything is encoded, and a contact sheet of the finished film.

## `scene list`

Each scene's start in the film, its length (its `seconds`, or its main box's frames),
its boxes with the main one marked, its layout file, chapter and cross. A scene whose
shot has no frames yet is listed with its length unknown, and says why.

## `scene preview`

Stills of one scene as the build draws its frames (before the scene's fades), into
`frames/scenes/NAME/at_S.png`: by default at its start, middle and end, or `--at S ...`,
or `--every S`. Nothing is encoded, so a layout's places and text are seen in seconds.

## `film lengths`

Each scene's planned length and, when its clip is built and current, its measured one,
and the film's, without building; then the chapters, each start as YouTube writes it.

## Contact sheet: `contact.png`

`film.check.contact` draws stills of the finished film on one picture, `contact.png`
beside the film, to check the words and their places without playing the film. Each
still is labelled with its film time, its scene and why it was taken; the captions are
drawn in place, as they show.

```python
from flowreel.film.scene_build import contact

contact("film.yml", at="caption")          # or "freeze", or "every:5"
```

| `at` | A still |
|---|---|
| `caption` (default) | at the middle of each timed text box |
| `freeze` | at the middle of each freeze of a main box |
| `every:S` | every `S` seconds from the start |

`columns` (default 4) and `width` (pixels of a still, default 480, at most the film's)
set the sheet's layout. The stills come from the scenes' clips, built when missing, so
no join is needed.

![A contact sheet every 0.25 s of a small film: the freeze holds one frame, the caption
runs across the cut](../../images/contact.png)
