# 1. Install

FlowReel runs in a conda environment. Clone the repository and run its installer:

```bash
git clone https://github.com/arunperiyal/FlowReel.git
cd FlowReel
./install.sh
```

The installer makes the environment `flexflow_env` (Python 3.12) from
`environment.yml`, with ffmpeg in it. If the environment already exists, it adds only
the packages it lacks. It installs FlowReel so that `git pull` updates it, and adds a
`flowreel` command to your shell's start-up file. Open a new terminal, then check:

```text
$ flowreel --version
flowreel 0.0.1
```

`./install.sh --help` lists its options. To install by hand instead:

```bash
conda env create -f environment.yml        # or: conda activate flexflow_env
conda activate flexflow_env
pip install --no-deps -e .
```

## Two ways to run commands

Each command can be run on its own, as in this tutorial:

```text
$ flowreel shot preview shots/wake.yml
```

Or start FlowReel's shell with `flowreel` alone and type the commands without the
`flowreel` in front. The shell remembers a project, so you can leave its folder out
(`use project:DIR`). See [commands](../../commands.md#the-shell).

## Rendering without a display

FlowReel draws its frames off screen, so a machine without a display (a cluster node, an
`ssh` session) renders the same frames. It picks the first back end that works: EGL on
a GPU, OSMesa on the CPU, or X. `flowreel shot render --backend osmesa` forces one. See
[rendering](../../rendering.md).

## Check

```text
$ flowreel --help
```

lists the command groups: `shot`, `camera`, `compose`, `film`, `project` and `jobs`,
and `doctor`. Every command has `--help` with examples, for instance
`flowreel project init --help`.

```text
$ flowreel doctor
```

checks what FlowReel runs on: the packages and their versions, ffmpeg, drawing without a
display, and the font. Its last line should read `everything FlowReel needs is here`;
anything marked `!` says what is wrong ([doctor](../../commands.md#doctor)).

Next: [the project and the data](02-project.md).
