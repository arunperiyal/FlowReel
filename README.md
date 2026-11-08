# FlowReel

Films of flow simulations from configuration files: rendered shots, 2D panels, layouts,
captions with mathematics, freezes, sound and assembly.

**Status:** planning. The design is in [docs/PLAN.md](docs/PLAN.md). The working
prototype, the scripts that made a 2-minute film of vortex-induced vibration for the
AFMS 2026 video competition, is in [prototype/afms/](prototype/afms/); the package in
`src/flowreel/` is being written from it.

## What it will do

- Read simulation output through adapters: flexflow PLT files first, VTK series, and
  parametric bodies made in code.
- Compute derived fields from velocity (vorticity, Q, lambda2, wall shear), never trusting
  stored derived fields that depend on the mesh.
- Render shots whose every property can change along the shot: camera, iso level,
  slice position, opacity, colour.
- Compose layouts and 2D panels, with live plots drawn at the film's frame rate.
- Build the film from one YAML file: cards, captions with `$...$` maths and arrows,
  freezes, frame-rate changes, fades and music, with caches keyed by content.
- Run headless on clusters, in parallel, with Slurm scripts written for it.

## Fonts

FlowReel bundles the Lato typeface by Łukasz Dziedzic, under the SIL Open Font Licence
1.1 (`src/flowreel/fonts/OFL.txt`).
