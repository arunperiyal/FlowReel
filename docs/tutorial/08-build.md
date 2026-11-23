# 8. Building the film

The frames are drawn (chapter 7), so the last step is to join them into the film.

## A preview first

```text
$ flowreel film build --preview 540
shot      planned  measured
title       3.00 s    3.00 s  built
wake        7.00 s    7.00 s  kept
sweep       3.00 s    3.00 s  kept
pressure    3.00 s    3.00 s  kept
end         4.00 s    4.00 s  kept
film       20.00 s   20.00 s  film.mp4
preview film_540p.mp4
srt film.srt
built in 2.3 s
```

`film build` makes each shot's **finished clip** (its frames at the film's rate, its
fades and its captions) and joins the clips into `film.mp4`. The clips `film check`
built are kept, since nothing changed: every clip has a key, and only a clip whose
frames, text or settings changed is made again ([clips](../clips.md)). The title card
has no caption, so `film check` did not need its clip, and it is built now. `--preview 540`
also writes `film_540p.mp4`, a small copy that is quick to send round for comments.

Each shot is listed with its **planned** length, worked out from `film.yml`, and its
**measured** length, read from the clip. They agree: 20 seconds.

The build also writes `film.srt`, subtitles made from the captions, so a player can show
them as text, or a screen reader can read them:

```text
1
00:00:03,600 --> 00:00:07,200
Vorticity, from the velocity alone
ω_z = ∂ v / ∂ x - ∂ u / ∂ y
```

## Change something

Edit a caption in `text/wake.yml` and build again: only the wake's clip is made again,
then the film is joined. Change the `range` in `shots/sweep.yml`: render that shot
again (only the frames that change are drawn), then build. That is the loop of making a
film: change a file, render or build, look.

```text
$ flowreel project info
project /home/you/films/cylinder
source:  vtk:../data/cylinder_crossflow/flow.pvd body cylinder=../data/cylinder_crossflow/cylinder.vtp
bodies:  cylinder
shots:   2
  shots/sweep.yml: sweep, 72 frames drawn (4 in drafts)
  shots/wake.yml: wake, 120 frames drawn (6 in drafts)
cameras: views main, approach_0000, approach_0096; tracks approach
film:    film.yml: 5 shots, 20.0 s planned
output:  frames/ 69.6 MB, clips/ 8.4 MB, .flowreel/ 512 B
```

lists what the project holds and the space its frames and clips take. `flowreel project clean` removes the caches; `--frames` and `--clips`
remove what took time to make, so they are only removed when you name them.

## On a cluster (optional)

On a machine with Slurm, the slow parts run as jobs. `--submit` writes a job script and
hands it to `sbatch`, and `--after` chains the jobs, so the whole film builds while you
are away:

```bash
flowreel shot render shots/wake.yml --submit            # prints a job id, say 1320
flowreel shot render shots/sweep.yml --submit           # 1321
flowreel compose panel panels/pressure.yml --submit     # 1322
flowreel film build --submit --after 1320 --after 1321 --after 1322 --preview 540
flowreel jobs status
```

The first render of a shot measures a frame before it sizes the job. [Slurm](../slurm.md)
says how a render is split into tasks, and how to describe a cluster FlowReel does not
know yet.

## What next

- The [user guide](../project.md) explains each part in full: the
  [layers](../layers-flow.md), [cameras](../cameras.md), [panels](../panels.md),
  [layouts](../layouts.md) that put shots and panels side by side, and
  [the film file](../film.md).
- The [rules](../rules.md) every project follows, on one page.
- Your own data: `flowreel project init` takes a folder of PLT files (`plt:CASE`), VTK
  files (`vtk:`) or a body made in code (`geometry:`); see [sources](../sources.md).
