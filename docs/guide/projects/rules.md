# Rules

FlowReel holds every project to a few rules. They are collected on this page so you can
learn them in one place instead of finding them one error at a time. Each rule gives its
reason and what happens when it is broken, and links to the page with the details. The
rules are decided in the plan (`plan/decisions.md`, Section 23). When a new rule is added, it
goes on this page in the same change.

## Projects

**1. A project is a folder with `flowreel.yml`.** Commands find it by walking up from the
file they are given, else from `use project:DIR` in the shell, else from the current folder.
*Why:* every command then puts its output in the same place, whichever folder you run it
from. *Broken:* outside a project the commands stop with an error saying how to make
one. `project init`, `shot template`, `film template` and the `jobs` commands work
anywhere, and the Python library has no such rule.
[Finding the project](project.md#finding-the-project)

**2. Output goes under the project root.** Frames go to `frames/` and clips to `clips/`.
Caches, measured frame costs and Slurm job records go to `.flowreel/`. This holds
wherever the command runs, unless `-o` (or `--clips`, `--slurm`) names another place.
*Why:* a render started in `shots/` and one started at the root must not make two copies.
[Where output goes](project.md#where-output-goes)

**3. Edit only what you can see.** `flowreel.yml`, `film.yml`, `cameras.yml` and your
files in `shots/`, `text/`, `cards/` and `assets/` are yours. `.flowreel/`, `frames/` and
`clips/` are FlowReel's. *Why:* deleting FlowReel's folders costs only the time to make
them again, so `project clean` can remove them safely. It never removes a file you wrote.
[Looking at a project, and cleaning it](project.md#looking-at-a-project-and-cleaning-it)

**4. One `cameras.yml`, at the project root.** It serves every shot and caption, and the
camera commands write to it unless given `-c FILE`. *Why:* a shot and a caption anchored
to the model must see the same views. *Broken:* a `cameras.yml` beside a file below the
root is an error saying to move it. FlowReel never reads it or silently skips it.
[One cameras.yml](project.md#one-camerasyml)

## Data and files

**5. Data is linked, never copied.** `project init --link` puts a symbolic link to the case
in `data/`, and `data/` is kept out of git. *Why:* a case can be hundreds of gigabytes, and
it belongs to the simulation, not the film.
[What is in it](project.md#what-is-in-it)

**6. A path in a file is relative to that file.** Examples are a shot's `source`, a film
shot's `frames`, a caption file and an `include`. *Why:* a file keeps working when the
folder around it is moved or copied. Paths typed on the command line are relative to
the current folder, as usual.

**7. Logos, pictures and music you use stay outside FlowReel's repository.** Keep them
in your project's `assets/`. Use only what you have the right to use. *Why:* FlowReel is
public, and a film's logos and licensed tracks belong to that film.
[Cards](../film/cards.md), [captions](../film/captions.md)

**8. Unknown keys are errors.** Every YAML file is checked when it is read. A misspelt key
or choice stops the command with the file, the key path and the nearest valid name.
*Why:* a key that was silently ignored would leave a film that looks wrong, with
nothing saying why. [Shot errors](../shots/shots.md#errors)

## The flow

**9. Derived fields come from velocity and pressure only.** A solver's stored
vorticity, Q or wall shear is ignored even when the grid has it. *Why:* in flexflow's
files those values are nodal sums that grow with the number of elements at a node. They
made the wall shear 4.6 times too large on bricks and 18.5 times on tetrahedra.
[Derived fields](fields.md)

**10. The flow is never interpolated in time.** A frame shows a saved step: the nearest
one, or the earlier at a tie. *Why:* an in-between flow would be made up, and showing
the earlier step means a frame never shows the flow later than asked.
[Time](../shots/shots.md#time), [panels](../composing/panels.md#where-the-flow-comes-from)

**11. A panel's colour range is given, not found from the data.** A panel coloured by a
field must be given its range. *Why:* a range taken from each frame would change from frame to frame,
so a colour would not mean the same value all through the film.
[Panels](../composing/panels.md#where-the-flow-comes-from)

**12. A shot's frame rate divides the film's.** In a film at 24 frames a second, a shot
may run at 8 or 12 frames a second, but not at 7. *Why:* each flow frame then lasts a
whole number of output frames, so live plots over a layout stay in step.
[Shots of a film](../film/film.md#shots)
