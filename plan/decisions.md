# FlowReel plan: decisions

Section 23: the decisions taken. They are not reopened; a new question goes in Section 24. The plan's other parts are listed in [README](README.md).

## 23. Decisions

| Topic | Decision (2026-11-08) |
|---|---|
| Name | FlowReel (command and package `flowreel`) |
| Home | `/media/arunperiyal/Works/projects/FlowReel`; public on GitHub as `arunperiyal/FlowReel` |
| Licence | MIT for FlowReel's code; the bundled Lato fonts stay under the OFL |
| Users | Mostly Arun; public, so documentation enough for others to start |
| Relation to flexflow | Independent; no wrapper; FlowReel reads flexflow's files itself |
| PLT reader | FlowReel keeps its own copy, tested against a small PLT written by the solver |
| Data formats, first release | flexflow PLT, OTHD and OISD, CSV series; plus `vtk` and `geometry` |
| Config and text format | YAML everywhere (Section 15) |
| Command layer | shellkit, one-shot and interactive (Section 13); public on GitHub, installed from there |
| Camera editor | Desktop window |
| Fonts | Lato bundled with its OFL licence |
| Environment | The existing `flexflow_env` conda environment (Python 3.12) on the laptop, workstation and airavata |
| AFMS prototype | Stays in the research repository as the record of the submitted film; this repository has a copy in `prototype/afms/` |
| When | Starting now, with Phase 1 next |
| Project rules (2026-11-22) | `flowreel.yml` stays the visible project file; machine state in a hidden `.flowreel/`; `project init` makes `shots/`, `text/`, `cards/`, `assets/`, `data/` and a `.gitignore`, `--link` symlinks the data; output under the project root; one `cameras.yml` at the root; commands stop outside a project (except `project init`, templates, `jobs`). Section 24 question 6, Section 19.8 |
| Tutorial data (2026-11-22) | pyvista's `cylinder_crossflow`: one steady 2D step at Re 35, converted to a `.pvd` with a thin span; Apache-2.0 (pyvista/data), checked: it may be shown in a film. Section 24 question 7, Section 19.8 |
| Presentation (2026-11-22) | The whole of `docs/` (not `PLAN.md`) as a MkDocs Material website on GitHub Pages: Tutorial, User guide, Reference; `mkdocs build --strict` on every PR, deployed on push to `main`. The tutorial one page per chapter in `docs/tutorial/`, a still per chapter and a short GIF of the film, rendered from the tutorial data once its licence allows. Section 24 question 8, Section 19.8 |
