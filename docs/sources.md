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
