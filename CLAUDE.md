# FlowReel

Python package (`src/flowreel/`) for building flow-visualisation films. Design: `docs/PLAN.md`
(decisions in Section 23, do not reopen). Hand-over notes: `SESSION.md`.

## Essentials
- Environment: `flexflow_env` (Python 3.12). Install with `pip install --no-deps -e .`.
- Config and text are YAML; command layer is shellkit.
- Derived fields come from velocity and pressure only (plan Section 6).
- No logos, licensed music or research data in the repo; tests use small generated data.
- `prototype/afms/` is a read-only reference for golden-frame tests.

## Rules (read the relevant file before acting)
- @.claude/rules/planning.md: phases, checkboxes in `docs/PLAN.md`
- @.claude/rules/git-workflow.md: branches, commits, stacked PRs, agents, no co-author lines
- @.claude/rules/documentation.md: documentation guidelines
- @.claude/rules/session-notes.md: `SESSION.md` is updated only on request

## Skills
- `stacked-pr`: create and maintain a stack of branches and PRs for a phase
- `phase-plan`: split a phase into tasks and branches in `docs/PLAN.md`
