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
when the case moves (`source: TAG` in shots comes with a later branch of Phase 9).

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
