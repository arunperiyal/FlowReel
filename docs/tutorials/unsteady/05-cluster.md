# 5. On a cluster

Each frame of a moving shot reads its own step: the 221 frames of the wake read 81 PLT
files of 9 MB, and took 3 minutes on a laptop with `-j 8`. A longer shot, or a 3D case,
is a job for a cluster. On a machine with Slurm:

```bash
flowreel shot render shots/wake.yml --submit            # a job array; prints its id, say 2001
flowreel compose panel panels/force.yml --submit        # 2002
flowreel compose layout layouts/board.yml --submit --after 2001 --after 2002
flowreel film build --submit --after 2003 --preview 540
flowreel jobs status
```

The first `--submit` of a shot measures one frame on a node, and sizes the job array
from it: how many frames each task draws, at how many at once, in how much memory
([Slurm](../../slurm.md)). The tasks draw consecutive runs of frames, and a task that
stops part way is submitted again as it is: frames drawn already are kept.

## What next

- Your own simulation: `flowreel project init plt:CASE` for PLT files, `vtk:` for VTK
  files ([sources](../../sources.md)), and each body's histories as CSV under it in
  `flowreel.yml` ([bodies](../../bodies.md#series)).
- More panels beside a shot: [panels](../../panels.md); a moving body followed by the
  camera: [cameras](../../cameras.md).
