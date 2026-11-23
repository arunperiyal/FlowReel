# FlowReel

Films of flow simulations from configuration files: rendered shots, 2D panels, layouts,
captions with mathematics, freezes, sound and assembly. Every picture is described by a
YAML file, so a film can be made again, changed in one place, or rendered on a cluster.

![A frame of the tutorial's film: the flow past a cylinder, coloured by vorticity](docs/tutorials/steady/images/04-camera.png)

**Documentation:** <https://arunperiyal.github.io/FlowReel/>, with
[the tutorial](https://arunperiyal.github.io/FlowReel/tutorials/steady/), a 20-second film from a
public data set in eight short chapters, and
[a second one](https://arunperiyal.github.io/FlowReel/tutorials/unsteady/) on a flow that
moves, read from PLT files with its force from CSV. The same pages are in
[docs/](docs/index.md).

**Status:** Phases 1 to 6 of [the plan](plan/README.md) are done: FlowReel rebuilt the
2-minute AFMS 2026 film of vortex-induced vibration from files, the same length with its
text in place, and rendered its shots on a Slurm cluster. Phase 7, the documentation, is
under way. The [prototype](prototype/afms/) the package was written from is kept for its
golden-frame tests.

## What it does

- **Reads simulation output** through adapters: FlexFlow's PLT files, VTK series
  (`.pvd`, `.vtu`) and bodies made in code. Long cases are read through windows.
- **Computes derived fields from velocity and pressure only** (vorticity, Q, lambda2,
  wall shear, forces), never trusting stored fields that depend on the mesh.
- **Renders shots** whose every property can change along the shot: the camera (picked
  by eye in a camera editor), iso levels, slice positions, colour ranges, opacity.
  Frames are cached by their content, so a change redraws only what it changes.
- **Composes layouts and panels:** shots side by side, and matplotlib plots drawn at
  the film's rate, with a dot moving along each history.
- **Builds the film from one YAML file:** cards, captions with `$...$` maths, arrows
  pinned to points of the model, freezes, frame-rate changes, fades, music, chapters,
  subtitles and a contact sheet.
- **Runs headless on clusters:** off-screen rendering, and Slurm jobs sized from a
  measured frame, written and submitted for you.

## Install

FlowReel runs in a conda environment, `flexflow_env` (Python 3.12) by default, the one
FlexFlow uses. Clone the repository and run the installer:

```bash
git clone https://github.com/arunperiyal/FlowReel.git
cd FlowReel
./install.sh
```

It finds conda, creates the environment from `environment.yml` (or, when it exists,
installs only the packages it lacks, so other tools in it keep their versions),
installs shellkit if missing, installs FlowReel editable (so `git pull` updates it),
checks ffmpeg, and adds a `flowreel` alias to `~/.bashrc` or `~/.zshrc` that runs it
without activating the environment.

| Option | Does |
|---|---|
| `-y`, `--yes` | answer yes to every question |
| `--no-alias` | leave the shell's start-up file alone |
| `--uninstall` | remove FlowReel and the alias; the environment stays |
| `CONDA_ENV_NAME=NAME ./install.sh` | use another environment |
| `SHELLKIT_DIR=DIR ./install.sh` | install shellkit from a local checkout, on a machine that cannot reach GitHub |

By hand, the same is:

```bash
conda activate flexflow_env
pip install --no-deps -e .
```

### ffmpeg

The film is encoded by ffmpeg, which pip cannot install. Install the conda-forge build
into the same environment:

```bash
conda install -n flexflow_env -c conda-forge ffmpeg
```

`environment.yml` lists the whole environment, ffmpeg included, for a new machine
(`conda env create -f environment.yml`).

FlowReel uses, in this order: the file named by `FFMPEG`, the `ffmpeg` beside the
environment's Python, then the one on the path. It checks the version (5.1 or later)
and the filters it needs once, and an error names the file it found. Other programs
install their own copies, which can come first on the path; Tecplot 360's
`bin/ffmpeg` (4.3) is one, and is too old.

## Tests

```bash
conda activate flexflow_env
python -m pytest -q
```

The suite makes its own small data; it needs no case files. Frames are drawn off screen
(OSMesa or EGL), so it runs over `ssh` and on a cluster node; tests that need a back end
the machine lacks are skipped and say why. It takes a few minutes; with `pytest-xdist`
installed, `python -m pytest -q -n auto --dist loadfile` spreads it over the cores.

CI (`.github/workflows/tests.yml`) runs it on every pull request and push to `main`,
twice: with every dependency at the oldest version `pyproject.toml` allows, and at the
newest. A new release of VTK or pyvista that breaks FlowReel then fails a check the day
it is out. The minimums, and why each is what it is, are in `pyproject.toml`.

## Licence

MIT, see [LICENSE](LICENSE).

## Fonts

FlowReel bundles the Lato typeface by Łukasz Dziedzic, under the SIL Open Font Licence
1.1 (`src/flowreel/fonts/OFL.txt`).
