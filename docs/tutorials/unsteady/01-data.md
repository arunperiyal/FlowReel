# 1. The data and its tag

## Get the data

As in the first tutorial, the data stays outside the project:

```text
$ cd ~/films
$ python ~/FlowReel/examples/tutorial_unsteady/get_data.py
downloading https://zenodo.org/records/5039610/files/fixed_cylinder_atRe100?download=1
downloading https://zenodo.org/records/5039610/files/Re100_fixe00.reactions?download=1
mesh: 64084 nodes a layer, 127189 triangles, 381567 tetrahedra, 628 nodes round the cylinder
converted 101 steps, t = 400 to 420, into cases/cylinder_re100/binary, and the force into cases/cylinder_re100/force.csv (179 rows)
next, in the project: flowreel data import plt --path cases/cylinder_re100/binary --tag re100
```

The data is a 2D simulation of the flow past a fixed cylinder of diameter 1 at a
Reynolds number of 100, published by Mouad Boudina under CC BY 4.0: it may be shown,
with credit ([the data](data.md)). The script checks each file's checksum, and turns the
flow, which comes as text, into what FlowReel reads: one **PLT file** a saved step, in
`cases/cylinder_re100/binary/`, and the force on the cylinder as a **CSV file**,
`cases/cylinder_re100/force.csv`. It keeps every second step of the near wake, 101
steps 0.2 time units apart; `--every` and `--box` change that.

## The project, and the case as a tag

```text
$ flowreel project init -o shedding --import plt:cases/cylinder_re100/binary --tag re100
linked shedding/data/re100/plt -> /home/you/films/cases/cylinder_re100/binary
wrote shedding/data/re100/domain.yml: fill in the units
made shedding: shots/ panels/ layouts/ assets/ data/
wrote shedding/film.yml, shedding/cameras.yml, shedding/.gitignore
wrote shedding/flowreel.yml; the case's bodies and units are in data/re100/domain.yml
$ cd shedding
```

`--import` makes the project and brings the case in at once, as `data import` would.
The kind is **`plt`**: it reads a folder of `<name>.<step>.plt` files, whatever wrote
them, and takes the step from the name and the time from the file. It finds the volume
and the wall zones by their cells: here `fluid` and `cylinder`
([sources](../../guide/projects/sources.md#the-plt-adapter)). Your own solver's PLT files
come in the same way. `project init` fitted the first view of `cameras.yml` to the case.

## The body and its force

The solver wrote the force on the cylinder too. A body's time histories are **series**:
CSV files with a `time` column, declared under the body, so a case with several bodies
gives each its own. A tag keeps them in its `series/` folder. Copy the force there:

```text
$ mkdir data/re100/series
$ cp ../cases/cylinder_re100/force.csv data/re100/series/
```

Then edit `data/re100/domain.yml`, replacing its `units:` and `bodies:` with:

```yaml
units:                            # the record's units: D, U and the density are 1
  rho: 1.0
  u_inf: 1.0
  mu: 0.01                        # rho U D / Re, with Re = 100
bodies:
  cylinder:
    zone: cylinder
    axis: z                       # the span: this 2D flow was given a thin one along z
    diameter: 1.0
    series:
      force: {file: series/force.csv}   # time, fx, fy, mz: copied in from the case
```

- **`units`**: the flow's constants in its own units, for the fields that take them,
  such as the pressure coefficient ([units](../../guide/projects/data.md#units)).
- **`axis` and `diameter`**: the flow is 2D, given a thin span along z, as in the
  first tutorial.
- **`series`**: `force.csv` holds `time, fx, fy, mz`, the drag, the lift and the
  moment the solver wrote. Its path is taken from the tag's folder. Any program that
  writes CSV will do ([bodies](../../guide/projects/bodies.md#series)); for a FlexFlow
  case, `data import history` writes the series itself
  ([histories from FlexFlow](../../guide/projects/data.md#histories-from-flexflow)).

```text
$ flowreel data check
re100: ok, 101 steps
```

Next: [a shot that moves](02-shot.md).
