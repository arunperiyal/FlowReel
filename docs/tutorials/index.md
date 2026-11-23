# Tutorials

Two tutorials, each making a short film from a public data set, with nothing but
FlowReel's commands and a few YAML files. Take them in order: the second assumes the
first.

1. **[A steady flow](steady/index.md)** (eight chapters, about an hour): one step of the
   flow past a cylinder at a Reynolds number of 35, read from VTK files. Installing
   FlowReel, a project, shots, the camera editor, a sweeping colour range, a panel of
   the pressure, captions, and the film; 20 seconds.
2. **[A flow that moves](unsteady/index.md)** (five chapters, about an hour): vortex
   shedding behind a cylinder at a Reynolds number of 100, read from PLT files, with the
   drag and lift beside it from a CSV file. A time track, a panel in a layout, placed
   captions, a freeze, and the render on a cluster; 17 seconds.

Every file each tutorial writes is under `examples/` (`examples/tutorial/project/` and
`examples/tutorial_unsteady/project/`), as it stands at the end, so you can compare
yours with it. The tests follow both, command by command, on generated stand-ins of
their data.
