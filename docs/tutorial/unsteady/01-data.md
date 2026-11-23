# 1. The data and the project

## Get the data

```text
$ mkdir ~/films/shedding && cd ~/films/shedding
$ python ~/FlowReel/examples/tutorial_unsteady/get_data.py
downloading https://zenodo.org/records/5039610/files/fixed_cylinder_atRe100?download=1
downloading https://zenodo.org/records/5039610/files/Re100_fixe00.reactions?download=1
mesh: 64084 nodes a layer, 127189 triangles, 381567 tetrahedra, 628 nodes round the cylinder
converted 101 steps, t = 400 to 420, into data/cylinder_re100/binary, and the force into data/cylinder_re100/force.csv (179 rows)
```

The data is a 2D simulation of the flow past a fixed cylinder of diameter 1 at a
Reynolds number of 100, published by Mouad Boudina under CC BY 4.0: it may be shown,
with credit ([the data](data.md)). The script checks each file's checksum, and turns the
flow, which comes as text, into what FlowReel reads: one **PLT file** a saved step, in
`data/cylinder_re100/binary/`, and the force on the cylinder as a **CSV file**,
`data/cylinder_re100/force.csv`. It keeps every second step of the near wake, 101
steps 0.2 time units apart; `--every` and `--box` change that.

## Make the project

```text
$ flowreel project init plt:data/cylinder_re100
made .: shots/ text/ cards/ assets/
wrote film.yml, cameras.yml, .gitignore
wrote flowreel.yml: 1 body (cylinder); fill in the supports
```

The source is **`plt:`** and a folder: the `plt` source reads a folder of
`<name>.<step>.plt` files (in it, or in a `binary/` folder in it), whatever wrote
them, and takes the step from the name and the time from the file. It finds the volume
and the wall zones by their cells: here `fluid` and `cylinder` ([sources](../../sources.md#the-plt-adapter)).
Your own solver's PLT files are read the same way.

## The body and its force

Edit `flowreel.yml`:

```yaml
bodies:
  cylinder:
    zone: cylinder
    axis: z                           # the span: this 2D flow was given a thin one along z
    diameter: 1.0
    series:
      force: {file: data/cylinder_re100/force.csv}   # time, fx, fy, mz
reference: {rho: 1.0, u_inf: 1.0}     # the record's units: D, U and the density are 1
```

- **`axis` and `diameter`**: the flow is 2D, given a thin span along z, as in the
  first tutorial.
- **`series`**: the body's time histories, each a CSV file with a `time` column.
  `force.csv` holds `time, fx, fy, mz`, the drag, the lift and the moment the
  solver wrote. A series is declared under its body, so a case with several bodies gives
  each its own files ([bodies](../../bodies.md#series)). Any program that writes CSV
  will do.
- **`reference`**: the flow's density and speed, here 1 as the record's units are, for
  fields such as the pressure coefficient ([reference values](../../project.md#reference-values)).

```text
$ flowreel project info
```

lists the source, `plt:data/cylinder_re100`, and the body. Next: [a shot that
moves](02-shot.md).
