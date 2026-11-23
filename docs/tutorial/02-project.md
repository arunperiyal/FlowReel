# 2. The project and the data

Every film lives in a **project**: a folder with a `flowreel.yml` in it. FlowReel's
commands find it from any folder inside it, and put what they make in the same places
every time ([projects](../project.md)).

## Get the data

Make a folder for the film anywhere outside the FlowReel repository, and get the data
into it:

```text
$ mkdir ~/films/cylinder && cd ~/films/cylinder
$ python ~/FlowReel/examples/tutorial/get_data.py
downloaded cylinder_Re35.case, cylinder_Re35.geo, cylinder_Re35.scl1, cylinder_Re35.scl2, cylinder_Re35.vel, LICENSE
converted to data/cylinder_crossflow/flow.pvd (29662 points, 14594 cells, span 0.1) and data/cylinder_crossflow/cylinder.vtp
```

(Change `~/FlowReel` to wherever you cloned it.) This is PyVista's `cylinder_crossflow`:
one steady step of a 2D flow past a cylinder of diameter 1 at a Reynolds number of 35.
The script checks each file's checksum, and converts the 2D mesh into a thin slab one
cell thick, because FlowReel's layers work on cells with volume. [The tutorial's data](data.md)
says what it does and why, where the data comes from, and its licence (Apache-2.0: you
may show it). No network? Add `--stand-in` for a small generated case of the same shape.

## Make the project

```text
$ flowreel project init vtk:data/cylinder_crossflow/flow.pvd --body cylinder=data/cylinder_crossflow/cylinder.vtp
made .: shots/ text/ cards/ assets/
wrote film.yml, cameras.yml, .gitignore
wrote flowreel.yml: 1 body (cylinder); fill in the supports
```

The **source** is `vtk:` and a file: the `vtk` adapter reads the `.pvd` collection of
flow files. The **body**, the cylinder's wall, is in a file of its own, and
`cylinder=` names it. `project init` made the folders for what you will write
(`shots/`, `text/`, `cards/`, `assets/`), a starting `film.yml`, a `cameras.yml` with one
view of the whole domain, and `flowreel.yml`:

```yaml
bodies:
  cylinder:
    zone: cylinder
    # axis: x                         # not slender, so not a beam: 0.9994 x 0.9997 x 0.1; give one to make it a beam
```

## Tell FlowReel about the body

`project init` measured the cylinder: 1 across and 0.1 along z, the thin span the
conversion gave it. Measured alone, that looks like a disc, not a cylinder. Its axis is
z, so say so, and give the diameter, since a body only 0.1 long is too short to measure
it along the span. Edit `flowreel.yml`:

```yaml
bodies:
  cylinder:
    zone: cylinder
    axis: z                           # the span: this 2D flow was given a thin one along z
    diameter: 1.0
```

The panel in chapter 6 cuts across the body's axis, so it needs this.

## Check

```text
$ flowreel project info
project /home/you/films/cylinder
source:  none (no shot yet)
bodies:  cylinder
shots:   none
cameras: views main; tracks none
film:    film.yml: 1 shot, length not known yet (shot 'cylinder': no frame_NNNNN.png files in /home/you/films/cylinder/frames/cylinder)
output:  frames/ 0 B, clips/ 0 B, .flowreel/ 0 B
```

`project info` lists what the project holds. It is nearly empty:

- **source** is read from the shots, and there are none yet; chapter 3 writes the first.
- **film** is the starting `film.yml` from `project init`: one shot, named after the
  folder, whose frames do not exist. Chapter 7 replaces it, so the complaint goes away.

A project made with `--link` (data kept elsewhere, [projects](../project.md)) would also
have a `data:` line. The folder now holds:

```text
cylinder/
├── flowreel.yml   cameras.yml   film.yml   .gitignore
├── shots/   text/   cards/   assets/
└── data/cylinder_crossflow/   flow.pvd  flow_0.vtu  cylinder.vtp  ...
```

Next: [a first shot](03-first-shot.md).
