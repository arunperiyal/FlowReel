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

## The `vtk` adapter

Reads a series of VTK files with pyvista: `flowreel.sources.vtk.VtkSource`. It is the
common denominator of research codes and ParaView exports, and it lets tests and examples
use small generated files.

```python
from flowreel import sources
wake = sources.create("vtk", path="out/wake_*.vtu", body="out/cylinder.vtp", dt=0.01)
wake.steps()                               # [100, 200, 300], from the filenames
wake.flow(200, ["U", "V", "W", "p"], Box((-1, -1, 0), (1, 1, 2)))
```

### Location, steps and time

| `path` is | steps | time of a step |
|---|---|---|
| a `.pvd` collection | `0, 1, 2, ...` in time order | the `timestep` written in the `.pvd` |
| a pattern, `out/wake_*.vtu` | the number the wildcard matches (`wake_0200.vtu` is step 200) | the step number, or `step * dt` |
| one file | `0` | `0` |

A `.pvd` numbers its steps by position because its files need not carry a number; a
pattern uses the number in the name so that a step means the same as in the solver's
output. A `.pvd` with several files at one time (parts) is refused: point it at one file
per step, such as a `.pvtu`.

### Options

| Option | Type | Default | Meaning |
|---|---|---|---|
| `path` | string | required | `.pvd` file, pattern or single file. Example: `out/wake_*.vtu` |
| `names` | mapping | `{}` | Standard name to the array's name in the files. Keys: `U`, `V`, `W`, `velocity`, `p`. Example: `{velocity: vel, p: P}` or `{U: ux, V: uy, W: uz}` |
| `body` | string | none | Wall surface: one file (used at every step), or a pattern or `.pvd` matched to the flow by step number. Example: `out/cylinder_*.vtp` |
| `body_block` | string or integer | none | Block holding the body, by name or index: in the `body` files if `body` is given, otherwise in the flow files, which are then multiblock (`.vtm`). Example: `wall` |
| `flow_block` | string or integer | the only block that is not `body_block` | Block holding the flow in multiblock flow files. Example: `fluid` |
| `dt` | number | `1` | Time of one step: `time = step * dt`. With a `.pvd` it replaces the file's times. Example: `0.01` |
| `times` | list or mapping | none | Explicit times: one per step in ascending step order, or `{step: time}`. Overrides `dt` and the `.pvd`. Example: `[0.0, 0.5, 1.5]` |
| `name` | string | `vtk` | Label of the source |

### Names

Without `names`, the adapter looks at the first step's arrays:

- `U`, `V`, `W`: scalar arrays of those names if present; otherwise the components of a
  three-component array called `velocity` (any case), or of a three-component `U`
  (OpenFOAM's convention).
- `velocity`: that vector, or `U`, `V`, `W` stacked.
- `p`: an array `p`, or `pressure` (any case).
- Any other array is offered under its own name. Sources do not vouch for stored derived
  fields; FlowReel computes its own from velocity and pressure.

`fields()` lists what can be provided, standard names first. Fields are point fields: an
array stored on cells is averaged to the points.

### Crop and memory

VTK's XML formats cannot read part of a mesh, so the adapter does the next best thing. It
reads **only the arrays the requested fields need**, crops at once, and only then builds
the fields. The crop keeps the cells with **every node inside** the box (edges included),
as the prototype does, so a cropped region never has ragged half-cells at its border. A
crop that keeps nothing returns an empty grid without arrays.

`memory_per_step(crop)` reads the first step's mesh without arrays, counts the points and
cells the crop keeps, and allows 8 bytes for every coordinate, connectivity entry and
array value in the files. It is an upper bound for a request of fewer fields. The whole
step is in memory for a moment while it is cropped; that peak is `memory_per_step(None)`.

`bounds()` is the bounding box of the first step. `series(name)` raises `KeyError`: VTK
files carry no time series. `body(step)` raises `LookupError` when neither `body` nor
`body_block` was given; a body stored as volume cells is reduced to its outer surface.

## The `geometry` adapter

A body built in code, for shots that need no data (the carving shot):
`flowreel.sources.geometry.GeometrySource`.

```python
carve = sources.create("geometry", body="grooved_cylinder",
                       params={"grooves": 4, "turns": 1.0}, frames=288)
carve.body(0)                    # the surface from the source's parameters
carve.build(cut_front=3.2)       # the same body with one parameter changed
```

| Option | Type | Default | Meaning |
|---|---|---|---|
| `body` | string | required | Name of a registered body. Example: `grooved_cylinder` |
| `params` | mapping | `{}` | The body's parameters, as plain values. A name the body does not take raises `TypeError` when the source is made. Example: `{grooves: 3, depth: 0.1}` |
| `frames` | integer | `1` | Number of steps; `steps()` is `0 .. frames - 1`. Example: `288` |
| `dt` | number | `1` | Time of one step: `time = step * dt`. Example: `0.0417` |
| `name` | string | `geometry` | Label of the source |

There is no flow: `fields()` is empty, `flow(...)` raises `LookupError` saying so, and
`series(name)` raises `KeyError`. `bounds()` and `memory_per_step()` describe the body
built from the source's parameters.

**Parameters and animation.** A body is a pure function of its parameters, so the same
values always give the same surface and a frame can be cached by them. `body(step)` does
not depend on the step. A shot animates a parameter by calling `build(**overrides)` with
that frame's values; this is the hook the tracks of the scene will use, which keeps the
source free of any notion of animation.

### Registering a body

```python
import pyvista as pv
from flowreel.sources.bodies import register_body

@register_body("smooth_cylinder")
def smooth_cylinder(span=12.0, radius=0.5):
    return pv.Cylinder(center=(span / 2, 0, 0), direction=(1, 0, 0),
                       radius=radius, height=span)
```

`available_bodies()` lists the names and `get_body(name)` returns the function.

### Body `grooved_cylinder`

A cylinder along **x**, from `x = 0` to `x = span`, with helical grooves. Angles around
the axis are measured as `atan2(y, z)`. All lengths share one unit; the defaults are the
AFMS helical case in diameters. With the defaults it gives the same surface as
`prototype/afms/render_carve.py`.

| Parameter | Type | Default | Meaning |
|---|---|---|---|
| `span` | number | `12.0` | Length of the cylinder |
| `radius` | number | `0.5` | Radius of the uncut surface |
| `grooves` | integer | `4` | Number of grooves, equally spaced around the body; `0` gives a smooth cylinder |
| `depth` | number | `0.08` | Radial depth at the middle of a groove |
| `width` | number | `0.2` | Chord width of a groove at the surface |
| `turns` | number | `1.0` | Turns each groove makes over the span; negative for the other hand, `0` for straight grooves |
| `phase` | number, degrees | `45.0` | Angle of the first groove at `x = 0` |
| `cut_front` | number or none | none | Carving progress: grooves exist for `x < cut_front`. None means fully carved. Example: run it from `-0.3` to `span + 0.3` |
| `cut_length` | number | `0.25` | Distance behind the front over which a groove reaches full depth |
| `glow_length` | number | `0.8` | Distance behind the front over which a new cut counts as fresh |
| `edge` | number, radians | `0.012` | Angle over which a groove wall turns, to keep it smooth to the eye |
| `samples` | pair of integers | `(721, 1441)` | Points along the span and around the body. Example: `(241, 361)` for a draft |
| `caps` | boolean | `true` | Close the two ends |

The surface carries two point arrays, both from 0 to 1, so the look stays the renderer's
choice (the prototype baked colours into the mesh):

- `groove`: how far the point is cut; 1 on a groove floor, 0 on the uncut surface.
- `fresh`: 1 just behind the cutting front, fading to 0 over `glow_length`; all 0 when
  `cut_front` is none. Use it for the glow behind the cutters.

`flowreel.sources.bodies.groove_angle(x, k, span=, grooves=, turns=, phase=)` gives the
angle in radians of groove `k` at `x`, for placing a cutter or an arrow on a groove.

## Example

`examples/sources_vtk_geometry.py` writes a small VTK series to a temporary folder, reads
it whole and cropped, and builds the grooved cylinder at three stages of carving:

```bash
PYTHONPATH=src python examples/sources_vtk_geometry.py
```
