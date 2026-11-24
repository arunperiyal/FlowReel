# Compose

!!! note "Going"
    This page is about the film of shots, which a [film of scenes](../film/film.md) replaces; it goes when nothing uses it ([about these pages](index.md)).

`compose` puts several folders of frames and matplotlib panels together in one
picture (plan Section 9). The pieces have their own pages:

| Page | What |
|---|---|
| [Layouts](layouts.md) | tiles of frame folders, shots at several `stations`, panel tiles, `rate: output` |
| [Panels](../shots/panels.md) | figures drawn per frame: `series`, `phase`, `map`, `locator`, `section`, `cuts`, `strip` |
| [Commands](../commands.md#compose-layout) | `flowreel compose layout` and `flowreel compose panel` |

## The AFMS comparison and lift map, from files

The film's comparison put two wakes on the left and live plots of displacement, lift
and drag on the right; its lift map showed sectional lift of both cases against span
and time, filling in. The prototype drew them with two scripts and settings in their
code (`compose_compare.py`, `render_extras.py liftmap`). With FlowReel they are four
files, as they were written for the film of shots (`examples/compare/` is now on a tag
and scenes: `data/cases/domain.yml`, `panels/`, `layouts/compare.yml`, `film.yml`):

```text
flowreel.yml   the two bodies and their series (CSV)
compare.yml    layout: two wake tiles and a panel tile of plots.yml, rate: output
plots.yml      series panel: three rows, both cases
liftmap.yml    map panel: both cases' sectional lift, one colour bar
```

```text
flowreel compose layout compare.yml     # frames/compare/
flowreel compose panel liftmap.yml -j 4 # frames/liftmap/
```

`python examples/compare/run.py DIR` writes the generated cases and plans and previews
both as scenes of a film.

## The check

Those two frames, composed from files by `flowreel compose`, are checked against
frames drawn by the prototype's own code (`tests/test_golden_compose.py`):

- `tools/make_compare_golden.py` has the prototype's `compose_compare.py` stack the two
  wakes and draw its plots at a time between two samples, laid on as its
  `make_film.py` does;
- `tools/make_liftmap_golden.py` has its `render_extras.py liftmap` draw the lift map
  from the same generated lift, written as its per-step files.

Only the inputs are the prototype's to read: the generated data, and the case names,
colours and labels it takes from `film_text.toml`. Both frames match to within the
limits of the golden shot tests: the comparison pixel for pixel, the lift map within
a thousandth of a grey level on average. A frame near each golden one (two wake frames
earlier, three map frames earlier) fails the same limits, and so do the comparison's
plots on their own.
