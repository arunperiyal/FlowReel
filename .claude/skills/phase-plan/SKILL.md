---
name: phase-plan
description: Split a FlowReel phase into checkbox tasks and three or more stacked branches in docs/PLAN.md. Use before starting a phase.
---

# Phase plan

1. Read the phase row in `docs/PLAN.md` Section 19 and the sections it references.
2. Break it into small tasks, each one commit-sized, as `- [ ]` items.
3. Group the tasks into three or more branches by kind of feature, named
   `phaseN/<kind>-<topic>`, ordered by dependency; mark which branches are independent
   (candidates for parallel agents).
4. Write the result under the phase in `docs/PLAN.md`, keeping the "done when" line.
5. Commit on its own branch/PR; ask the user to confirm the breakdown before implementing.
