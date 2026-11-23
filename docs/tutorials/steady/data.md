# The tutorial's data

The tutorial uses one public data set: **`cylinder_crossflow`** from PyVista's example
data. It is one steady step of a 2D flow past a cylinder of diameter 1 at a Reynolds
number of 35. At that Reynolds number the wake holds two vortices attached behind the
cylinder and does not shed. It is small (0.7 MB), free to show, and needs no account to
download.

## Getting it

In the tutorial's project folder:

```text
$ python examples/tutorial/get_data.py
downloaded cylinder_Re35.case, cylinder_Re35.geo, cylinder_Re35.scl1, cylinder_Re35.scl2, cylinder_Re35.vel, LICENSE
converted to data/cylinder_crossflow/flow.pvd (29662 points, 14594 cells, span 0.1) and data/cylinder_crossflow/cylinder.vtp
```

`get_data.py DIR` puts it under `DIR` instead of the current folder. A second run
downloads nothing and rewrites nothing:

```text
$ python examples/tutorial/get_data.py
data/cylinder_crossflow/ensight: all files there already, with the right checksums
data/cylinder_crossflow: converted already; nothing changed
```

It does not rewrite the files because FlowReel's frame keys include each data file's
modification time. Rewriting the same data would cause every frame to be drawn again.

**Without the network**, `--stand-in` writes a small case of the same shape instead. It
has the same file names, blocks and fields, on a coarse mesh of about 500 cells, with
potential flow past the cylinder: no wake, but a velocity and pressure that vary over
the whole domain. The tutorial's commands work on it unchanged, and FlowReel's tests use
it. Its `README.md` says it is a stand-in. To swap it for the real data, remove
`data/cylinder_crossflow/` and run the script again without `--stand-in`.

## What you get

```text
data/cylinder_crossflow/
├── ensight/          the case as published: cylinder_Re35.case, .geo, .scl1, .scl2, .vel
├── flow.pvd          one step (time 0)
├── flow_0.vtu        the flow: U, V, W, p
├── cylinder.vtp      the cylinder's wall
├── LICENSE           Apache-2.0
├── README.md         source, author, citation, checksums
└── converted.json    what the conversion was made from (used by a second run)
```

The flow is read with the `vtk` adapter:

```yaml
source:
  adapter: vtk
  path: ../data/cylinder_crossflow/flow.pvd
  body: {cylinder: ../data/cylinder_crossflow/cylinder.vtp}
```

The paths in a shot are relative to the shot file, here in `shots/` ([rules](../../guide/projects/rules.md)).

## What the conversion does, and why

The case is EnSight Gold as exported by ANSYS Fluent. FlowReel reads VTK files, and its
layers expect cells with volume. So the script:

- **Gives the 2D mesh a span:** one cell across, 0.1 diameter wide, from z = -0.05 to
  z = 0.05. Triangles become wedges and quadrilaterals become hexahedra, so a slice at
  z = 0 cuts through the middle of every cell. VTK 9.7 changed the order of a wedge's points
  (which way round its base goes), so the script asks the installed VTK and converts
  again if it changes. The fields are the same on both faces, so
  every z-derivative is zero, as it is in 2D.
- **Renames the fields:** `velocity` is split into `U`, `V` and `W` (`W` is zero), and
  `pressure` becomes `p`.
- **Drops `vorticity_mag`:** FlowReel computes every derived field from velocity and
  pressure only, and never uses a solver's stored one ([rules](../../guide/projects/rules.md), [fields](../../guide/projects/fields.md)).
- **Extrudes `wall_cylinder`** in the same way into the surface `cylinder.vtp`, the body,
  and closes it with a flat cap at each end, its faces turned outwards. Without the caps
  it would be an open tube, and a camera looking along it, as the tutorial's does, would
  see through it into the background. The other boundaries (`inlet`, `outlet`, `outlet_top`, `outlet_bottom`) are not needed.

Units are the solver's. The free stream is 35 along +x, and `p` is the static pressure
as Fluent exported it. The domain is x 0 to 15 and y -3.75 to 3.75, and the
cylinder's centre is at (2.5, 0).

## Source, licence and citation

| | |
|---|---|
| Where | `Data/EnSight/CylinderCrossflow/` in [pyvista/data](https://github.com/pyvista/data), commit `f114d31d`; also `pyvista.examples.download_cylinder_crossflow()` |
| Made by | Matthew Flamm, with ANSYS Fluent 20.1, added to pyvista/data in June 2021 ([pull request 2](https://github.com/pyvista/data/pull/2)) |
| Licence | Apache-2.0, the licence of pyvista/data; the data set has none of its own |
| May it be shown in a film? | Yes. Apache-2.0 allows the data to be copied, changed and shown. A copy of the data must carry the licence and a notice; `get_data.py` writes both beside it |

**It is for pictures, not numbers.** Its author says it "was not generated with
accuracy as the goal, e.g. predicting drag coefficient, and was not validated in any
way". Use it to learn FlowReel, not to quote a drag coefficient.

**How to cite it**, in a film's credits or a paper:

> Cylinder in crossflow at Re 35, by Matthew Flamm, from the PyVista example data
> (https://github.com/pyvista/data), Apache-2.0.

For PyVista itself: C. B. Sullivan and A. Kaszynski (2019), "PyVista: 3D plotting and
mesh analysis through a streamlined interface for the Visualization Toolkit (VTK)",
*Journal of Open Source Software* 4(37), 1450, https://doi.org/10.21105/joss.01450.

## Checksums

The script downloads from a fixed commit and checks each file's SHA-256. If a checksum
does not match, the file is refused, deleted, and the script stops. A copy changed or
damaged on the way never reaches the tutorial.

| File | SHA-256 |
|---|---|
| `cylinder_Re35.case` | `683956c15c786730bf07596a2a8480eb1de091ba81c57fde6d656f63f1520a32` |
| `cylinder_Re35.geo` | `5c58108fdb00d5ff306f9b594c423f1634e700197ac0cde9312deab7d8a58dda` |
| `cylinder_Re35.scl1` | `c489f3af25ce0df23e24933da47aecd3bb64a964f364856e1efe18a54f03f2da` |
| `cylinder_Re35.scl2` | `c5713b63c643c0f9de20c6a1135de9f383740f8eb33fd430db552b85a9aaa2f5` |
| `cylinder_Re35.vel` | `aa21f382ea6b189f2b18bf871d6f1352c64b772ad18584b87828ba0ab81cf9b2` |
| `LICENSE` | `b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1` |

## From Python

| Function in `examples/tutorial/get_data.py` | Does |
|---|---|
| `get(folder, stand_in=False)` | the whole script; returns `folder/data/cylinder_crossflow` |
| `fetch(url, path, sha256)` | download one file unless it is there already, checking its checksum |
| `convert(case, out)` | the EnSight case to `flow.pvd`, `flow_0.vtu` and `cylinder.vtp` |
| `write_stand_in(folder)` | the small generated case |
