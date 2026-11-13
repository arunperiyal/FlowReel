# Derived fields

`flowreel.fields` computes every derived quantity from **velocity and pressure only**.
A solver's stored vorticity, Q or wall shear is never used: in flexflow's PLT files those
are nodal sums that grow with the number of elements at a node, which made the wall shear
4.6 times too large on bricks and 18.5 times on tetrahedra (`docs/PLAN.md`, Section 6).
A grid may carry arrays named `vorticity` or `Q`; they are ignored.

## Computing fields

```python
from flowreel import fields

grid = source.flow(step, ["U", "V", "W", "p"], crop)
out = fields.compute(grid, ["lambda2", "vorticity_x"])       # one gradient for both
grid["lambda2"] = out["lambda2"]

wall = fields.compute(grid, ["skin_friction", "sectional_force"],
                      wall=source.body(step), mu=1.0, rho=1000.0, u_inf=1.0, axis="x")
```

- `grid` is a pyvista dataset with `U`, `V`, `W` (or the vector `velocity`) and, for the
  pressure fields, `p` as point data. It is not modified.
- `compute` returns `{name: value}` for the requested names. Each field declares the
  fields it needs; `compute` orders them and evaluates each **once per call**, so the
  velocity gradient is computed once however many fields ask for it. Ask for all the
  fields of a frame in one call.
- Parameters are keyword arguments. A missing required parameter, or one that no
  requested field accepts (a typo), raises `TypeError`.
- `fields.available()` lists the names; `fields.describe(name)` gives a field's needs and
  parameters; `fields.resolve(names)` gives the evaluation order.
- Units are the source's own: a gradient is velocity over length, a stress has the unit
  of pressure, and so on.

## Volume fields

One row per grid point.

| Field | Shape | Definition | Needs | Parameters |
|---|---|---|---|---|
| `velocity` | (n, 3) | raw input: `velocity`, or `U V W` stacked | point data | |
| `pressure` | (n,) | raw input `p` | point data | |
| `velocity_gradient` | (n, 3, 3) | `G[i, j] = d u_i / d x_j` | `velocity` | |
| `vorticity` | (n, 3) | curl of velocity | `velocity_gradient` | |
| `vorticity_x`, `_y`, `_z` | (n,) | components of `vorticity` | `vorticity` | |
| `Q` | (n,) | `(‖Omega‖² - ‖S‖²) / 2` | `velocity_gradient` | |
| `lambda2` | (n,) | middle eigenvalue of `S² + Omega²` | `velocity_gradient` | |
| `speed` | (n,) | `‖u‖` | `velocity` | |
| `velocity_relative` | (n, 3) | `u - body_velocity` | `velocity` | `body_velocity` |
| `pressure_coefficient` | (n,) | `(p - p_inf) / q` | `pressure` | `rho`, `u_inf`, `p_inf = 0` |

`S = (G + Gᵀ) / 2` is the strain rate and `Omega = (G - Gᵀ) / 2` the rotation; norms are
Frobenius norms. `q = rho u_inf² / 2` is the reference dynamic pressure.

### Meaning and sign

- **`velocity_gradient`**: row is the velocity component, column the direction of the
  derivative, so `G[0, 1] = dU/dy`. It is VTK's point gradient: at a node, the mean of
  the gradients of the elements sharing it. This is what the plan prescribes, because it
  does not depend on how many elements meet at the node.
- **`vorticity`**: twice the local rotation rate of the fluid. Right-handed:
  `vorticity_z = dV/dx - dU/dy` is positive for anticlockwise rotation seen from +z.
  Solid-body rotation with angular velocity `omega` has vorticity `2 omega`.
- **`Q`**: positive where rotation exceeds strain, which marks the inside of a vortex;
  negative where strain dominates. Solid-body rotation gives `Q = ‖omega‖²`.
- **`lambda2`** (Jeong and Hussain 1995): **negative** inside a vortex core, so
  isosurfaces are drawn at negative levels (the prototype uses -1). Solid-body rotation
  gives `-‖omega‖²`. It is less noisy than Q in a strained wake, at the cost of an
  eigenvalue problem per node.
- **`speed`**: magnitude of velocity, never negative.
- **`velocity_relative`**: the flow as seen from the body. `body_velocity` is one
  `(3,)` vector (rigid translation) or an `(n, 3)` array, in the grid's frame and unit.
- **`pressure_coefficient`**: 1 at a stagnation point of steady inviscid flow, negative
  where the pressure is below the free stream's (suction). `rho` and `u_inf` are
  required: a silent default of 1 would be wrong for a dimensional source.

### Accuracy of the gradient

The point gradient is exact for a velocity that varies linearly. For a curved profile it
is second-order at interior nodes of a regular hexahedral grid. **At a boundary node only
the elements on the inner side exist, so the gradient is one-sided and first-order.**
That affects the outermost layer of a cropped region and, more importantly, the wall
(below). The tests measure this on a Burgers vortex with 8 nodes across the core radius:
0.8% of the peak vorticity on hexahedra, 1.0% on tetrahedra in the interior and 2.9% on
their boundary nodes.

## Wall fields

One row per **cell** of the wall surface, which is passed as the parameter `wall`
(a `pyvista.PolyData` of polygons in the grid's coordinates, for example
`source.body(step)`).

| Field | Shape | Definition | Needs | Parameters |
|---|---|---|---|---|
| `wall_frame` | `WallFrame` | normals, areas, centres, matched flow nodes | grid points | `wall`, `wall_normals = "auto"`, `wall_tolerance` |
| `wall_normal` | (c, 3) | unit normal `n`, from the wall into the fluid | `wall_frame` | |
| `wall_area` | (c,) | cell area | `wall_frame` | |
| `wall_pressure` | (c,) | `p` on the wall cell | `pressure`, `wall_frame` | |
| `wall_shear` | (c, 3) | tangential part of `mu (G + Gᵀ) n` | `velocity_gradient`, `wall_frame` | `mu` |
| `skin_friction` | (c, 3) | `wall_shear / q` | `wall_shear` | `rho`, `u_inf` |
| `wall_traction` | (c, 3) | `-(p - p_inf) n + wall_shear` | `wall_pressure`, `wall_shear`, `wall_frame` | `p_inf = 0` |
| `sectional_force` | `SectionalForce` | traction times area, summed over strips | `wall_traction`, `wall_frame` | `axis`, `sections = 32`, `span` |
| `wall_force` | `WallForce` | traction times area, summed over the wall; its moment | `wall_traction`, `wall_frame` | `about = (0, 0, 0)` |

### Normal direction and sign convention

- **`n` points from the wall into the fluid**, that is, out of the body.
- **Stresses and forces are those the fluid exerts on the wall** (on the body).
- The traction on the wall is `t = -(p - p_inf) n + tau_w`: pressure pushes the wall
  against its normal, and the wall shear `tau_w` drags it along the flow.
- `tau_w` is the tangential part of `mu (grad u + grad uᵀ) n`:
  `tau - (tau · n) n`. It points the way the fluid next to the wall moves relative to
  the wall. For `U = g y` over a wall at `y = 0` with the fluid above (`n = +y`),
  `tau_w = (mu g, 0, 0)`: positive along the flow, and **negative where the near-wall
  flow is reversed**, which is how separation is read from it. For the wall on the other
  side (`y = 1`, `n = -y`) the same flow gives `(-mu g, 0, 0)`.
- The normal viscous stress is left out of the traction. It vanishes on a no-slip wall
  in incompressible flow, and what the one-sided gradient returns for it is noise.
- `mu` is the dynamic viscosity (`rho nu`, or `rho U D / Re`). It is the molecular
  one: the eddy viscosity is zero at the wall.

### How the wall is sampled

Following `prototype/afms/surface_data.py`: each wall node takes the gradient (and
pressure) of the **nearest flow node**, and a wall cell the mean over its corners. The
wall's nodes are expected to be nodes of the flow grid. If one lies farther than
`wall_tolerance` from every flow node (default 1e-6 of the wall's bounding-box
diagonal), a `RuntimeWarning` says how far, since the stress is then sampled off the
wall. `WallFrame.gap` holds that largest distance.

Because wall nodes are boundary nodes, the gradient there is one-sided: the wall shear
is first-order in the height `h` of the first cell, with an error of about
`mu (h / 2) d²u/dy²`. In the tests, `U = a y + b y²` gives an error of exactly `mu b h`,
halving with `h`, and a cylinder with a first cell of 0.2% of its radius is within 0.3%. The prototype's integrated forces were within 4% of
the solver's on the bare case.

### Orienting the normals

`wall_normals` chooses how `n` is made to point into the fluid:

- `"auto"` (default): the winding is made consistent, then each connected part of the
  wall is turned towards the nearest flow nodes that are not on the wall. This does not
  depend on the surface's winding, and works for open walls and for bodies with grooves.
- `"keep"`: trust the surface's own winding (right-hand rule).
- `"flip"`: the reverse of `keep`.

Use `keep` or `flip` for a zero-thickness wall with fluid on both sides, where `auto`
cannot know which side is meant.

### Sectional force

`sectional_force` cuts the wall into `sections` equal strips along `axis` (`"x"`, `"y"`,
`"z"` or 0, 1, 2: the span of the body), over `span = (lo, hi)` or the wall's own extent,
and sums `wall_traction * wall_area` in each. A cell belongs to the strip holding its
centre; cells outside the span are left out. The result has:

| Attribute | Meaning |
|---|---|
| `axis` | 0, 1 or 2 |
| `position` | (sections,) strip centres along the axis |
| `width` | strip length along the axis |
| `force` | (sections, 3) force **on the body** per strip |
| `per_length` | `force / width` |
| `total` | sum over the strips, (3,) |

Sectional coefficients are `per_length / (q D)`, for example `CL = per_length[:, 1] / (q D)`
when lift is along y. `p_inf` does not change the force on a closed section.

### Total force and moment

`wall_force` sums `wall_traction * wall_area` over the whole wall. It needs no axis, so it
is the one to use for a body that is not slender: a sphere, a wing, a bluff body.

| Attribute | Meaning |
|---|---|
| `force` | (3,) force **on the body**, in the source's force unit |
| `moment` | (3,) moment of that load about `about`: the sum of `r x dF`, `r` from `about` to each wall cell's centre (right-hand rule) |
| `about` | (3,) the reference point, default the origin |

Pass one body as `wall` to get the load on that body alone:

```python
load = fields.compute(grid, "wall_force", wall=src.body(step, "flap"), mu=mu,
                      about=hinge)["wall_force"]
```

Coefficients are the caller's: divide `force` by `q` times a reference area and `moment`
by `q` times area times length. `p_inf` changes neither on a closed body.

**Checked on** Stokes flow past a sphere, where the traction is `3 mu U / (2a)` along the
stream everywhere and the drag is `6 pi mu a U`. On a shell of wedges with 33 306 nodes
the wall shear is within 2.1% of the traction and the drag within 1.5%; with 48 layers on
a finer sphere, 0.3% and 0.2%. The error is the one-sided gradient at the wall
(first order in the height of the first cell).

## Adding a field

```python
from flowreel.fields import register

@register("enstrophy", needs="vorticity")
def enstrophy(grid, vorticity, *, scale=1.0):
    """Half the squared vorticity."""
    return 0.5 * scale * (vorticity ** 2).sum(axis=1)
```

The function receives the grid, then the value of each need in order. Keyword-only
arguments are its parameters; those without a default are required. A field must take
what it uses from its needs, never from stored arrays on the grid.
