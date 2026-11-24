# 6. On a cluster

Each frame of a moving shot reads its own step: the 221 frames of the wake read 81 PLT
files of 9 MB, and took 3 minutes on a laptop with `-j 8`. A longer shot, or a 3D case,
is a job for a cluster. On a machine with Slurm:

```bash
flowreel shot render shots/wake.yml --submit            # a job array; prints its id, say 2001
flowreel film build --submit --after 2001 --preview 540
flowreel jobs status
```

The first `--submit` of a shot measures one frame on a node, and sizes the job array
from it: how many frames each task draws, at how many at once, in how much memory
([Slurm](../../guide/making/slurm.md)). The tasks draw consecutive runs of frames, and a task that
stops part way is submitted again as it is: frames drawn already are kept. The build
draws the panel itself, so it only waits for the shot.

## What next

- Your own simulation: `flowreel data import plt --path CASE --tag NAME` for PLT files,
  `vtk` for VTK files ([data and tags](../../guide/projects/data.md)), and each body's
  histories as CSV under it in the tag's `domain.yml`
  ([bodies](../../guide/projects/bodies.md#series)).
- Two cases side by side: two tags in one project, a layout of a shot box of each, and
  a panel whose lines name `tag.body`
  ([bodies across tags](../../guide/projects/data.md#shots-and-panels-name-a-tag)).
- More panels beside a shot: [panels](../../guide/shots/panels.md); a moving body followed by the
  camera: [cameras](../../guide/shots/cameras.md).
