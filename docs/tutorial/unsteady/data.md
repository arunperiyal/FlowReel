# The tutorial's data: vortex shedding at Re = 100

## What it is

Mouad Boudina, "Numerical simulation data of a two-dimensional flow around a fixed
circular cylinder", Polytechnique Montréal, 2021, Zenodo record 5039610,
[doi:10.5281/zenodo.5039610](https://doi.org/10.5281/zenodo.5039610). It was computed
with Cadyf, a finite-element fluid-structure code, at a Reynolds number of 100, the
cylinder held still. Lengths are in diameters, speeds in the free stream's, and the
density is 1.

**Licence:** Creative Commons Attribution 4.0 International (CC BY 4.0). It may be shown
and shared, the film included, with credit to its author, as the tutorial's title card
gives it. The converted data stays out of the repository (`data/` is ignored); the
pictures of these pages are made from it by `examples/tutorial_unsteady/stills.py`.

## Getting it

`examples/tutorial_unsteady/get_data.py PROJECT` downloads two of the record's files and
checks each one's SHA-256 (pinned in the script, after checking them against the MD5
sums the record publishes):

| File | Size | What |
|---|---|---|
| `fixed_cylinder_atRe100` | 1.17 GB | the flow, text: `Re Ur`, `Nt N`, then for each of 201 steps (t = 400 to 420) its time and N = 82,872 lines `x y U V p` |
| `Re100_fixe00.reactions` | 329 kB | the force on the cylinder, `t Fx Fy Mz`, t = 0 to 500 |

`--stand-in` writes a small generated flow in the same formats instead, and converts it:
the tests follow the tutorial on it. It is not the real data, and its `README.md` says
so.

## What the script does to it

- **Makes a mesh.** The flow file has nodes, not elements. The nodes are triangulated
  (Delaunay) and the triangles inside the box kept (default x from -3 to 15, y from -5
  to 5: the near wake), with those inside the cylinder left out. The nodes do not move,
  so this is done once.
- **Gives it a span**, 0.1 diameter along z, and cuts each prism into three
  tetrahedra, the cells a PLT volume zone holds; neighbouring prisms cut their shared
  face alike. The cylinder's wall is a closed surface of triangles, its ends capped.
- **Writes a PLT file a kept step** (default every second: 101 files, 0.2 time units
  apart, about 940 MB), named `cylinder.<step>.plt` with the step `t * 10`, and the
  time in the file. `W` is 0.
- **Writes the force** for the kept times as `force.csv`, `time, fx, fy, mz`, unchanged.

`converted.json` records the files' sums and the options, so running the script again
does nothing unless one of them changed.

**What it shows.** The lift swings with a period of 6.07 time units, a Strouhal number
of 0.165; the mean drag coefficient is 1.33 and the lift's amplitude 0.32, as other
simulations at Re = 100 find.
