# Data and tags

A project's data comes in by **tag**: each case in a folder of its own under `data/`,
described by a `domain.yml` beside it. A tag is one case: its flow (PLT or VTK files,
linked, never copied), what was made from it (`series/`), its units and its bodies.

```text
data/
├── bare/                      a tag: one case
│   ├── domain.yml             what the case is
│   ├── plt/    -> the folder the case's PLT files are in   (a link)
│   └── series/                force.csv, sections.csv ...
└── helical/
    ├── domain.yml
    └── plt/    -> ...
```

**Why tags.** A film often shows several cases side by side, and cases made the same way
name their zones alike: the AFMS film's smooth and grooved cylinders are both `cyl`. A
body, its units and its series belong to its case, so each tag declares its own, and two
tags may both have a body called `cyl`. Shots name a tag, so a shot file does not change
when the case moves ([below](#shots-and-panels-name-a-tag)).

## Bringing a case in

```text
$ flowreel data import plt --path /scratch/run/binary --tag smooth
linked data/smooth/plt -> /scratch/run/binary
wrote data/smooth/domain.yml: fill in the units (docs/guide/projects/data.md#units)
```

`data import` links the folder the case's files are in as `data/TAG/plt` (or `vtk`) and
writes `domain.yml` with what it measured: the reader's options, each wall zone as a body
with its axis and diameter, and `measured:` (steps, times, zones, fields, bounds). The
units are left for you: FlowReel cannot know them from the files. Then edit the file:
it is yours.

- **Link, or copy.** A link costs nothing, and the case stays where the simulation put
  it. `--copy` copies the files instead (for a small case you will move to another
  machine), after saying their size; above 5 GB it asks for `--yes`. A copy's SHA-256
  sums are kept under `measured.checksums`.
- **Importing again.** A tag holds one case: a second import into it is refused unless
  `--force`, which points the link at the new folder and replaces `measured:`, but keeps
  every other line of `domain.yml`, your units and bodies included. A tag of another kind
  is always refused; import it under a new tag.
- **VTK.** `--path` is the folder of the flow files; its one `.pvd` is the flow, or name
  it with `--flow`. Bodies in separate files are given by name, `--body cylinder=FILE`; a
  file outside the folder is linked beside `domain.yml`.
- **Geometry.** A body made in code, no files: `data import geometry --name
  grooved_cylinder --param grooves=4 --tag carve`.
- **With a new project.** `project init --import plt:PATH --tag TAG` makes the folders
  and imports the case, and fits `cameras.yml`'s first view to it.

## Histories from FlexFlow

```text
$ flowreel data import history --path /scratch/run --tag smooth
othd group 0: series/othd_0.csv, 98000 rows, 49 nodes; declared as cyl's displacement
oisd group 0: series/oisd_0.csv, 2000 rows; declared as cyl's force
```

A FlexFlow case writes its time histories as text: probe data in `othd_files/*.othd`,
surface data in `oisd_files/*.oisd`. `data import history` links those folders into the
tag as `othd/` and `oisd/` and converts each **group** once to CSV under `series/`. The
tag must hold its flow already (`data import plt` first). `--path` is the case folder,
or one of the two folders.

- **Groups.** A file may hold several groups, one per probe set (`othId`) or surface
  (`osgId`). Each becomes its own CSV, `othd_N.csv` or `oisd_N.csv`, so two bodies' rows
  are never mixed. When the tag has one body and a file has one group, the group is
  declared under that body. Otherwise name each with `--group N=BODY` (the same `N` in
  both kinds). Groups left over are listed as comments in `domain.yml`, to move under
  their body by hand.
- **What is declared.** An OTHD group with `aleDisp` becomes the body's `displacement`,
  with `by: node` and its columns named `dx`, `dy`, `dz`. An OISD group with `totTrac`
  becomes its `force`, with `fx`, `fy`, `fz`. Any other group is declared as `othd_N` or
  `oisd_N`. Every variable the files hold is kept in the CSV (`avePres`, `totArea`,
  the pendulum's lines), in columns named after it (`aleDisp_y`).
- **Restarts and runs.** The files are read as FlexFlow Analyzer reads them. The runs
  `<problem>N.othd` are taken in the order of `N`, from `archive/` and `cleaned/`
  (following `cleaned/.runs.json`), then any in the older flat layout. Without numbered
  runs, the compiled file is read. A run that resumed earlier than the last one reached
  writes some times again, and at such a time the later run's values win.
- **Again.** A second `data import history` into the tag needs `--force`, which writes
  the CSVs and their declarations again. Re-importing the flow (`data import plt
  --force`) keeps the history and its series.

What was found is kept under `measured.history`: the files read, and each group's rows,
nodes and variables.

## Series from the flow: `data extract`

Some series are not written by the solver but computed by FlowReel from the tag's flow.
`data extract KIND TAG` writes them under the tag's `series/` and declares them under the
body in `domain.yml`. The constants come from the tag's [units](#units), so nothing is
typed twice.

### `sections`

```text
$ flowreel data extract sections smooth -j 8
cyl: 121 of 121 steps to compute (0 in cyl_sections.csv already), 48 sections over x = 0 to 12
wrote data/smooth/series/cyl_sections.csv (121 new steps) and cyl_sections_stations.csv
declared as cyl's sections in data/smooth/domain.yml
```

The force on a body's sections along its axis, step by step. The wall is cut into equal
sections along the body's axis, fixed at the first step's extent. The traction on each
section (pressure, and wall shear from the flow next to the wall) is summed and divided
by the section's length. The result is `fx, fy, fz`, a force per unit length on the body.

- **Units.** The shear needs `units.mu`. `p_inf` is taken from the units too (default 0).
  With `rho` and `u_inf`, and the body's `diameter`, the coefficients `cx, cy, cz` are
  written as well, divided by `q D` with `q = rho u_inf^2 / 2`.
- **Files.** `series/<body>_sections.csv` holds `time, section, fx, fy, fz[, cx, cy,
  cz]`, and `series/<body>_sections_stations.csv` holds `section, station`. They are
  declared as the body's `sections`, with `by: section` and the stations file.
- **Going on.** A step whose time is in the file already is kept. A run cut short goes
  on where it stopped, and a longer `--steps` window adds only its new steps. `--force`
  starts the file again (another `--sections` count needs it) and replaces a
  declaration of `sections` you wrote yourself.
- **Options.** `--body` (default the tag's one body), `--axis` (default the body's),
  `--sections N` (48), `--steps FIRST LAST`, `--every N`, `--margin L` (flow read round
  the wall, 0.5), `-j N` (steps at once, one process each).

A [`map`](../composing/panels.md#map) panel draws it against the span and time.

## Shots and panels name a tag

```yaml
# shots/wake.yml
source: smooth                       # the tag: data/smooth/
```

```yaml
source: {tag: smooth, margin: 1.0}   # with a reading option of the tag's kind
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `source.tag` | tag name | required in the mapping form | the case, under `data/<tag>/`; `source: bare` alone says the same |
| `source.kind` | `plt`, `vtk` or `geometry` | the tag's | the tag's kind, checked: another is an error |

Other keys of the mapping are reading options of the tag's kind ([`source`](#source)).

A shot (and a flow panel: `section`, `cuts`, `strip`) whose `source` is a tag reads the
case as its `domain.yml` says: the reader and its options, the bodies, and the units as
the parameters of the derived fields (a pressure coefficient needs no `params`). The
mapping form adds reading options of the tag's kind ([`source`](#source)). It may say the
`kind` too, which must be the tag's. A shot's frames are keyed by the tag's kind, options
and units, so editing them draws the frames again.

**Bodies across tags.** Within a shot, a body is named as its tag names it (`body: cyl`).
A panel of series is not tied to one case, so its bodies come from every tag. There a
body is `tag.body`, and a body's own name is enough when only one tag has it:

```yaml
# panels/lift.yml: the two cylinders, both declared as cyl in their tags
type: series
rows:
  - lines:
      - {body: smooth.cyl, series: force, column: fy, label: smooth}
      - {body: helical.cyl, series: force, column: fy, label: helical}
```

Naming `cyl` alone there is an error that lists `smooth.cyl` and `helical.cyl`. The
bodies of `flowreel.yml`, while it still has them, are named as before.

`project info` and `flowreel doctor` list the tags, and say when a tag's link does not
resolve.

## Looking after the tags

| Command | What it does |
|---|---|
| `data list` | each tag: kind, steps, size, and where its link points, or that it does not resolve |
| `data info TAG` | steps and times, zones, fields, bounds, units and bodies |
| `data info PATH` | the same for any folder of PLT or VTK files; no project needed |
| `data check [TAG ...]` | links resolve, sources open, units given, series files there; exit status 1 if not |
| `data rename OLD NEW` | the folder, and every file that names it: `source:`/`tag:` values, `OLD.body` names, `tags:` |
| `data remove TAG` | the tag's folder: links (never what they point at), `domain.yml`, series; `--yes` for a copy |

A case that moved shows in `data list` and `data check` as a link that does not
resolve; `data import ... --force` with the new path mends it and keeps your edits.

The example `examples/data_tags/run.py` does all of this on two generated cases.

## `domain.yml`

```yaml
kind: plt                       # plt, vtk or geometry
source: {path: plt}             # the reader's options; paths from this folder
units: {rho: 1000.0, mu: 1.0, u_inf: 1.0, length: 1.0}
bodies:
  cyl:
    zone: cyl
    axis: x
    diameter: 1.0
    series:
      force: {file: series/force.csv}
```

`flowreel data template` prints one with every key, each with a comment
(`--kind vtk` or `geometry` for those kinds).

| Key | Type | Default | Meaning |
|---|---|---|---|
| `kind` | `plt`, `vtk` or `geometry` | required | how the case is read: the [source](sources.md) of that name |
| `source` | mapping | `{}` | the reader's options ([below](#source)); paths are taken from the tag's folder |
| `units` | mapping | `{}` | the case's constants ([below](#units)) |
| `bodies` | mapping | none | the case's bodies, as [bodies](bodies.md) declares them; series paths from the tag's folder |
| `measured` | mapping | none | what `data import` found (steps, zones, fields, bounds); for reading, never read back |

The tag's name is its folder's: letters, digits, `-` and `_`. No dots: a body of another
tag is written `tag.body` where several tags meet.

## `source`

The options of the tag's reader, as the [sources](sources.md) page gives them; a path is
taken from the tag's folder.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `path` | path | required (`plt`, `vtk`) | the PLT folder, or the VTK flow (a `.pvd`, a pattern or a file) |
| `volume` | text | found in the file | `plt`: the volume zone |
| `body` | text, list, or name to file | found | `plt`: wall zone(s); `vtk`: body files by name; `geometry`: the body made in code |
| `nen`, `window`, `margin`, `cache` | | | `plt`: as the [sources](sources.md#the-plt-adapter) page says |
| `names`, `body_block`, `flow_block`, `times` | | | `vtk`: as the [sources](sources.md#the-vtk-adapter) page says |
| `params` | mapping | `{}` | `geometry`: the body's parameters |
| `frames`, `dt` | | `1`, `1.0` | `geometry`: its steps and their time |
| `name` | text | the kind | the source's label |

## Units

The case's constants, in its own units: two tags may differ (a case in water beside one
in air). They are the parameters of the [derived fields](fields.md) that take them, so a
shot or a panel of the tag needs no `params` of its own.

| Key | Type | Default | Meaning |
|---|---|---|---|
| `units.rho` | number > 0 | none | density |
| `units.mu` | number > 0 | none | dynamic viscosity: wall shear, skin friction, sectional force |
| `units.u_inf` | number > 0 | none | free-stream speed |
| `units.p_inf` | number | `0` | free-stream pressure |
| `units.length` | number > 0 | none | the length lengths are shown in: the axes layer's `unit: diameters` |

A shot's [frames are keyed](../rendering/rendering.md) by its tag's units too, so changing
them draws the frames that use them again.
