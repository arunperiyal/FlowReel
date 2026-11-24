# 2. The project and its data

Every film lives in a **project**: a folder with a `flowreel.yml` in it. FlowReel's
commands find it from any folder inside it, and put what they make in the same places
every time ([projects](../../guide/projects/project.md)). The data comes in as a **tag**:
a case of the project, under `data/<tag>/`, described by its own `domain.yml`
([data and tags](../../guide/projects/data.md)).

## Get the data

The data stays outside the project, as a simulation's output would. Make a folder for
your films, and get the data into it:

```text
$ mkdir ~/films && cd ~/films
$ python ~/FlowReel/examples/tutorial/get_data.py
downloaded cylinder_Re35.case, cylinder_Re35.geo, cylinder_Re35.scl1, cylinder_Re35.scl2, cylinder_Re35.vel, LICENSE
converted to cases/cylinder_crossflow/flow.pvd (29662 points, 14594 cells, span 0.1) and cases/cylinder_crossflow/cylinder.vtp
next, in the project: flowreel data import vtk --path cases/cylinder_crossflow --tag crossflow --body cylinder=cases/cylinder_crossflow/cylinder.vtp
```

(Change `~/FlowReel` to wherever you cloned it.) This is PyVista's `cylinder_crossflow`:
one steady step of a 2D flow past a cylinder of diameter 1 at a Reynolds number of 35.
The script checks each file's checksum, and converts the 2D mesh into a thin slab one
cell thick, because FlowReel's layers work on cells with volume. [The tutorial's data](data.md)
says what it does and why, where the data comes from, and its licence (Apache-2.0: you
may show it). No network? Add `--stand-in` for a small generated case of the same shape.

## Make the project

```text
$ flowreel project init -o cylinder
made cylinder: shots/ panels/ layouts/ assets/ data/
wrote cylinder/film.yml, cylinder/cameras.yml, cylinder/.gitignore
wrote cylinder/flowreel.yml; bring a case in with data import
$ cd cylinder
```

`project init` made the folders, a starting `film.yml`, a `cameras.yml` with a first view,
a `.gitignore`, and `flowreel.yml`, which marks the folder as a project.

## Bring the case in as a tag

```text
$ flowreel data import vtk --path ../cases/cylinder_crossflow --tag crossflow --body cylinder=../cases/cylinder_crossflow/cylinder.vtp
linked data/crossflow/vtk -> /home/you/films/cases/cylinder_crossflow
wrote data/crossflow/domain.yml: fill in the units (docs/guide/projects/data.md#units)
```

The case is now the tag `crossflow`. Nothing was copied: `data/crossflow/vtk` is a link
to the folder. The kind is `vtk`: the reader of `.pvd` collections of VTK files (a
folder of PLT files would be `plt`, as in the [second tutorial](../unsteady/index.md)). The
cylinder's wall is in a file of its own, and `--body cylinder=` names it. Every shot
will now say only `source: crossflow`.

## Tell FlowReel about the case

`data import` measured what it could and wrote it in `data/crossflow/domain.yml`. Two
things the files cannot say are left to you.

- **The units.** The case is without dimensions: the cylinder's diameter, the
  free-stream speed and the density are all 1, and the Reynolds number is 35, so the
  viscosity is 1/35. Derived fields that need them (a pressure coefficient, the wall
  shear) take them from here.
- **The body.** `data import` measured the cylinder: 1 across and 0.1 along z, the thin
  span the conversion gave it. Measured alone, that looks like a disc. Its axis is z,
  so say so, and give the diameter, since a body only 0.1 long is too short to measure
  it along the span. The panel in chapter 6 cuts across the axis, so it needs this.

Edit `data/crossflow/domain.yml`, replacing its `units:` and `bodies:` with:

```yaml
units:                            # the case is without dimensions: D = 1, U = 1, Re = 35
  rho: 1.0
  u_inf: 1.0
  mu: 0.028571                    # rho U D / Re
bodies:
  cylinder:
    zone: cylinder
    axis: z                       # the span: this 2D flow was given a thin one along z
    diameter: 1.0
```

Leave the rest of the file as it is. `measured:` at its end is what `data import` found
(the steps, fields and bounds), for you to read.

## Check

```text
$ flowreel data check
crossflow: ok, 1 steps
$ flowreel project info
project /home/you/films/cylinder
source:  none (no shot yet)
tags:    crossflow (vtk, 1 steps)
bodies:  crossflow.cylinder
shots:   none
cameras: views main; tracks none
film:    film.yml: 1 shot, length not known yet (shot 'cylinder': no frame_NNNNN.png files in /home/you/films/cylinder/frames/cylinder)
output:  frames/ 0 B, clips/ 0 B, .flowreel/ 0 B
```

`data check` looks at every tag: its link, its source, its units, its series. `project
info` lists what the project holds. It is nearly empty: **source** is read from the
shots, and there are none yet; **film** is the starting `film.yml`, which chapter 7
replaces. The folders now hold:

```text
films/
├── cases/cylinder_crossflow/   the data: flow.pvd, flow_0.vtu, cylinder.vtp, ...
└── cylinder/                   the project
    ├── flowreel.yml   cameras.yml   film.yml   .gitignore
    ├── data/crossflow/   domain.yml, vtk -> ../../cases/cylinder_crossflow
    └── shots/   assets/   ...
```

The `.gitignore` leaves the data out of git, but keeps `domain.yml`: you edited it.

Next: [a first shot](03-first-shot.md).
