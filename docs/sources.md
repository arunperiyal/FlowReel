# Sources

A **source** gives FlowReel the data of one simulation. Everything else (fields, scenes,
films) talks to the `Source` interface in `flowreel.sources`, so adding a file format means
adding an adapter, nothing more.

## What a source provides

| Method | Returns |
|---|---|
| `steps()` | saved step numbers, ascending |
| `time(step)` | physical time of the step |
| `fields()` | names of the point fields available |
| `flow(step, fields, crop)` | `pyvista.UnstructuredGrid` with those fields, cropped to a `Box` or `None` |
| `body(step)` | wall surface (`PolyData`), deformed to that step |
| `bounds()` | `Box` of the whole domain |
| `series(name)` | `pandas.DataFrame` with a `time` column plus values |
| `memory_per_step(crop)` | estimated GB for one step, used to choose the number of jobs |

## Naming and units

- Velocity is `U`, `V`, `W` (or the vector `velocity`); pressure is `p`. Adapters map their
  own names onto these.
- Units are the source's own. A `scales:` block in `flowreel.yml` may declare
  `length: D`, `velocity: U` for labels.
- Derived fields (vorticity, Q, lambda2, wall shear, ...) are **not** provided by sources;
  they are computed from velocity and pressure.

## Cropping

`Box(lo, hi)` is an axis-aligned box. Adapters apply the crop while reading where the format
allows it, so a frame never holds the whole domain when it needs only a region.
`Box.from_bounds` and `Box.to_bounds` convert from and to VTK's
`(xmin, xmax, ymin, ymax, zmin, zmax)` order.

## Registering an adapter

```python
from flowreel import sources
sources.register("mycode", MySource)   # factory called with the source's options
src = sources.create("mycode", path="case/")
```

Packages can instead declare the entry-point group `flowreel.sources`:

```toml
[project.entry-points."flowreel.sources"]
mycode = "mypackage.adapter:MySource"
```

`sources.available()` lists all adapters; an unknown name raises `KeyError` with that list.

## The `flexflow` adapter

Reads a FlexFlow case folder with FlowReel's own reader for the solver's Tecplot binary
files (`flowreel.sources.flexflow.plt`); FlexFlow itself is not needed.

```python
from flowreel.sources.flexflow import FlexflowSource
src = FlexflowSource("cases/cylinder_12")
src.steps()                       # [5000, 5005, ...]
flow = src.flow(5000, ["U", "V", "W", "p"], crop=None)
wall = src.body(5000)
lift = src.series("force")
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `path` | path | required | the case folder; PLT files are `binary/<name>.<step>.plt`, or in the folder itself |
| `volume` | text | `FIELD` | name of the volume zone |
| `body` | text | `cyl` | name of the wall zone |
| `nen` | integer | from the file | nodes per element of the volume zone, when the file's zone type is wrong |
| `name` | text | `flexflow` | label of the source |

- **Time** is the solution time stored in each file.
- **Position:** the files hold the deformed mesh, so the flow and the body are at the
  step's position; `dispX`, `dispY`, `dispZ` give the displacement.
- **Fields:** `U`, `V`, `W`, `p` (the file's `Pressure`) and the other stored variables
  (`dispX`, `dispY`, `dispZ`, `eddy`, `orderPar`). The stored `xVor`, `yVor`, `zVor` and
  `QCriterion` are **not provided**: they are nodal sums that depend on the mesh. Ask
  `flowreel.fields` for vorticity and Q instead.
- **Crop** keeps the cells with every node inside the box. The file is read before the
  crop, so the crop saves memory afterwards but not while reading.
- **Series:** `displacement` from `othd_files/*.othd` (columns `time`, `probe`, `dx`,
  `dy`, `dz`; `probe` is the row in the file, from 0) and `force` from
  `oisd_files/*.oisd` (columns `time`, `fx`, `fy`, `fz`, the total force, not a
  coefficient). Where restarts repeat a time, the later file wins.

The test data in `tests/data/flexflow_case/` is a small piece of real output (half of the
boundary layer over one spanwise cell, two steps), cut with `tools/cut_plt.py`.
