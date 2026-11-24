# FlowReel plan: questions

Section 24: questions, open and decided. The plan's other parts are listed in [README](README.md).

## 24. Questions

New ones are added here as the work raises them.

| # | Question | Needed by |
|---|---|---|
| 1 | For a 500 diameter case: nodes and size of one PLT file, and whether the whole domain is saved. Not known until the runs start; until then windowed reading is tested on a generated file. | Phase 2B, branch 6 |
| 2 | `data table --output` writes one node per file. A history along the whole span (49 probes and more) needs one export of all nodes in long form. Asked of FlexFlow Analyzer in its `docs/FLOWREEL.md`; until then, a loop over nodes. | Phase 2B, branch 2 |
| 3 | ~~Should frame keys (and Phase 2B's window index) include each data file's size and modification time?~~ **Decided 2026-11-18: yes**, done in Phase 2B branch 6; the span index is keyed by its file's the same way. | Phase 2B, branch 6 |
| 4 | ~~Where do the AFMS film's own FlowReel files live?~~ **Answered 2026-11-19:** in a FlowReel project folder of their own, outside this repository (they name a logo and a licensed track). How a project folder is made and laid out is question 6. | Phase 4, branch 7 |
| 5 | ~~Are the AFMS film's rendered frames still on the workstation?~~ **Answered 2026-11-19:** yes; Arun copies them into the AFMS project folder when branch 7 needs them. | Phase 4, branch 7 |
| 6 | ~~Project rules~~ **Decided 2026-11-22** (Arun's proposal, discussed after the backend): (a) `flowreel.yml` stays the visible project file, for what is edited by hand; a hidden `.flowreel/` folder holds only machine state (caches, measured timings). (b) Outside a project the commands stop with an error saying how to make one, except `project init`, the `template` commands and `jobs`; the Python library works anywhere. (c) Generated output (`frames/`, `clips/`, `.flowreel/`) goes under the project root, wherever a command is run from; `-o` still overrides. (d) One `cameras.yml`, at the project root, for every shot and caption. Paths written in files stay relative to the file. Confirmed the same day: the folders `project init` makes (`shots/`, `text/`, `cards/`, `assets/`, `data/`, with `film.yml` and `cameras.yml` at the root), a `.gitignore` for the generated ones and `data/`, and `init --link` putting a symlink to the data in `data/` (data is never copied); a `cameras.yml` beside a shot file is an error that says to move it to the root. | Phase 7, branch 1 |
| 7 | ~~Which public data set does the tutorial use?~~ **Decided 2026-11-22: pyvista's `cylinder_crossflow`** (`pyvista.examples.download_cylinder_crossflow`). Looked at: 0.7 MB of EnSight (`cylinder_Re35.case`), one steady step of a 2D flow past a cylinder of diameter 1 at Re 35, domain x 0 to 15, y -3.75 to 3.75, z 0; blocks `fluid` (14 831 points, quads and triangles) with `velocity`, `pressure` and `vorticity_mag` (the last not used, Section 6), the boundaries `inlet`, `outlet`, `outlet_top`, `outlet_bottom`, and the wall `wall_cylinder`. **Licence checked 2026-11-22 (branch 2): it may be shown.** The files are in `pyvista/data` (`Data/EnSight/CylinderCrossflow/`), added in June 2021 by Matthew Flamm, a PyVista maintainer, who made it with ANSYS Fluent 20.1 and exported it as EnSight Gold (pyvista/data PR 2). He says it "was not generated with accuracy as the goal ... and was not validated": good for pictures, not for numbers. It has no licence of its own, so the repository's applies: Apache-2.0, which allows copying, changing and showing it, a film and stills from it included, provided the licence and a notice go with any copy of the data. `get_data.py` writes both beside the data. | Phase 7, branch 2 |
| 8 | ~~How is the documentation, and the tutorial in it, presented?~~ **Decided 2026-11-22** (asked before branch 2): (a) a website, MkDocs Material on GitHub Pages, rather than Markdown read on GitHub, a notebook or a walkthrough inside the shell; (b) it covers all of `docs/` in three parts, Tutorial, User guide and Reference, and leaves out `PLAN.md`; (c) `mkdocs build --strict` on every PR, deployed on every push to `main`; (d) the tutorial one page per chapter under `docs/tutorial/`; (e) a still at the end of each chapter and a short GIF of the finished film, rendered from `cylinder_crossflow` by a script, committed once its licence allows. | Phase 7, branches 3 and 4 |
| 9 | matplotlib 3.11 lays text out a few pixels lower than 3.10 (its text layout changed; setting the old `text.hinting`, `text.kerning_factor` and `mathtext.default` does not bring it back), so captions, cards and panel labels no longer match the golden pictures drawn by the prototype. Until this is decided FlowReel declares `matplotlib<3.11` (Phase 8, branch 1). Lift the cap by placing text from the font's own metrics (the same on every version) and accepting new golden pictures drawn by FlowReel, or keep the prototype's pictures and the cap? | Before matplotlib 3.10 leaves conda-forge's newest builds |
| 10 | ~~What is the adapter that reads PLT files called, and where do time series come from?~~ **Decided 2026-11-23** (Arun): the adapter is `plt`, named after the files it reads rather than the solver that wrote them, since FlowReel does not depend on FlexFlow; `flexflow` stays as its second name so existing shots keep working. Time series come from CSV files declared in `flowreel.yml`; FlexFlow's `.othd` and `.oisd` reading stays as Section 23 has it. Both go into the second tutorial. | Phase 8, branches 9 and 10 |
| 11 | ~~How does a project hold its data, and several cases at once?~~ **Decided 2026-11-24** (Arun, in six rounds of questions): by tag. Each case under `data/<tag>/`, linked (or copied with `--copy`, after a size check), with its own `domain.yml` (written by `data import`, edited by hand) holding its units, its bodies and their series; a tag may hold several kinds (`plt` or `vtk`, `othd`, `oisd`, `series`; `geometry` for bodies made in code). Shots name a tag (`source: bare`); across tags a body is `tag.body`. OTHD and OISD are converted once to CSV per group, with FlexFlow Analyzer's handling borrowed in. `flowreel.yml` keeps `defaults:` and `tags:`. No project uses the old layout, so it is replaced, not kept. `project init` makes folders only; `project sections` becomes `data extract sections`; `compose`, `doctor` and `jobs check` stay. This replaces, for the data's layout and what `flowreel.yml` holds, the answers of question 6 and question 10. The details are in Section 19.10. | Phase 9 |

**Decided 2026-11-13: both PLT and VTU.** FlowReel reads flexflow's PLT files itself
and also VTU files, among them those FlexFlow Analyzer extracts (`field extract`); the
user picks per project with `flexflow:CASE` or `vtk:FILE.pvd`. VTU is the general path
for any solver and for a small window made once. PLT stays because:

- **No second copy of the data.** The reference case is 155 MB a step; a shot of 120
  steps is 19 GB of PLT and about as much again in VTU, written before the first frame.
- **Long cases.** A PLT stores each variable as one block, so a window can be read
  without loading the file (Section 17). A VTU is read whole, so every window, and every
  position of a travelling window, would be an extract made beforehand.
- **The reader exists,** is tested against solver output, and loads a step in 1.5 s.

Everything else FlowReel would have had to know about a flexflow case is dropped: no
`domain.yml`, no `.def`, no OTHD or OISD groups. What FlexFlow Analyzer is asked to add
for this (a `flowreel.yml` writer, all nodes in one CSV) is listed in that repository's
`docs/FLOWREEL.md`.

Answered 2026-11-13: each cylinder is its own surface zone in the PLT; the risers to
come are pin-roll with top tension; bodies and boundary conditions are written in
`flowreel.yml`; time histories come as CSV from FlexFlow Analyzer. This narrows
Section 23's "Data formats, first release": OTHD and OISD stay for one-body cases only.
