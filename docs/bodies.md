# Bodies

A source's files say where a body's surface is and nothing else: not which way its span
runs, how thick it is, or how its ends are held. FlowReel does not look for that in the
solver's other files. It is written once, in the project's `flowreel.yml`, and every
shot uses the body by its name.

Code: `flowreel.project` (`load_project`, `find_project`), `flowreel.project.bodies`
(the records), `flowreel.project.names` (names in shots), `flowreel.project.measure`
(centre, centreline, diameter). A runnable example on generated data is
`examples/bodies/run.py`.

## The project file

A project is a folder with `flowreel.yml`. A shot uses the nearest one: in the shot
file's own folder, or the nearest folder above it. So `films/afms/flowreel.yml` serves
`films/afms/shots/carve.yml`. So far the file holds `bodies:`; other keys come with the
phases that use them.

```yaml
bodies:
  riser:
    zone: cyl                      # surface zone in the source; default: the body's name
    axis: x                        # span direction; leave out for a body that is not slender
    diameter: 1.0                  # reference length
    ends:
      - {at: 0.0, support: pinned}
      - {at: 500.0, support: roller, free_along: x, tension: true}
    series:
      displacement: {file: data/riser_disp.csv, by: node, stations: data/riser_nodes.csv}
      force: data/riser_force.csv
  downstream:
    zone: cyl2
    axis: x
    ends: [{at: 0.0, support: clamped}, {at: 12.0, support: clamped}]
```

`flowreel project init SOURCE` writes this block with one body per surface zone, its
axis and diameter measured, and the supports left to fill ([commands](commands.md#project-init)).

## A body

| Key | Type | Default | Example |
|---|---|---|---|
| `zone` | the source's surface zone (a name from `source.bodies()`) | the body's name | `zone: cyl` |
| `axis` | `x`, `y` or `z`: the span direction | none: the body is not slender | `axis: x` |
| `diameter` | positive number, source length unit: symbols and stations scale with it | measured from the surface when needed | `diameter: 1.0` |
| `ends` | list of supports (below); needs `axis` | none | `[{at: 0, support: clamped}]` |
| `series` | mapping of series names to CSV files (below) | none | `force: data/force.csv` |

Two bodies cannot share a zone. Lengths are in the source's own unit, and a station is a
plain number along the axis, not a formula.

## Names in shots

With a project, a body name in a shot is a declared name. It reaches the source as the
body's `zone`, so a layer's `body: riser`, a camera's `follow: riser` and
`source.body(step, "riser")` (as wall fields take it) all read zone `cyl`.

- **No declaration is needed to draw a body.** Zones that no body claims keep their own
  names, as without a project.
- **A name may be left out** where one body is meant: `follow: true` takes the only
  declared body, or else the source's only zone. With several, FlowReel asks for a name.
- A wrong name is reported with the names there are and the nearest one.
- A body layer's default `body: all` still draws every zone.
- The declarations are part of every frame's key: give `riser` another zone and the
  frames that show it are drawn again.

From Python, `Scene.make`, `render` and `render_frame` find the project themselves from
the shot file. For a shot built in code, pass the source wrapped:
`flowreel.project.names.declare(source, load_project("films/afms"))`.

## Stations, centre and diameter

Where a body has an `axis`, its **centre at a station** is the mean of the surface
points within a thin slab of the station, so `follow` (and later `supports` and
`centreline`) work on a bent and moving body. The slab is a quarter of the declared
diameter; without one, 2% of the body's length but no more than a quarter of its width,
so a body 500 diameters long is cut into thin slices and not slabs 10 diameters wide.
`follow` takes its axis from the declaration unless the camera gives `axis`.

The **diameter** measured from the surface (by `project init`, and where a declaration
leaves it out) is twice the median distance of a section's points from the section's
own axis, taken as the median over sections along the span. Medians make grooves,
strakes and the ends count for little: the grooved cylinder of the carving shot
measures 1.0, its bare diameter. A body without an axis takes the smallest side of its
bounding box. `project init` gives a body an `axis` when it is at least three times
longer in one direction than across.

| Function | Gives |
|---|---|
| `measure.centre(surface, station, axis)` | the section's centre, `(x, y, z)` |
| `measure.centreline(surface, axis, stations=None, count=33)` | `(stations, centres)`, centres `(n, 3)` |
| `measure.diameter(surface, axis=None)` | the diameter |
| `measure.long_axis(surface)` | `x`, `y`, `z` or `None` |

## Supports

How the solver holds the structure is not in its files. It is written under the body's
`ends`, each at a station along the axis. A support may also sit along the span.

| `support` | Fixes | Its own keys |
|---|---|---|
| `clamped` | position and slope | |
| `pinned` | position; the body may turn | |
| `roller` | position across `free_along`; slides along it | `free_along: x` (required) |
| `spring` | nothing; restrained by `stiffness` | `stiffness: 20` (required, positive) |
| `free` | nothing | `mark: true` draws a thin ring |
| `prescribed` | moved by the solver along `direction` | `direction: y` or `[0, 1, 0]` (required) |

Any support takes `tension: true`, for a riser held by top tension. Two supports cannot
share a station. The `supports` layer that draws them is the next part of this phase;
the declarations are read and checked now.

## Series

A body's time histories are CSV files, whatever wrote them (for flexflow, FlexFlow
Analyzer's `data table --output`). A file is given by path alone (`force:
data/force.csv`) or with these keys:

| Key | Meaning | Default |
|---|---|---|
| `file` | the CSV, relative to the project folder | required |
| `time` | name of the time column | `time` |
| `columns` | names to use for columns, `{dy: aleDisp_y}` | the file's own |
| `by` | a column numbering the points along the body (`node`), for a history at many points | none: one row per time |
| `stations` | where those points are: a list of numbers, or a CSV of `node, station`; needs `by` | none |

The series are declared and checked here; reading them (`source.series(name,
body=...)`) and series tracks come in the next branches of this phase.
