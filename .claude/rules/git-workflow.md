# Git workflow

## Branches and PRs
- Never commit to `main` (a local hook blocks it). Work on branches, push, open PRs.
- Always use **stacked PRs**: each branch is based on the previous branch of the stack, and
  its PR targets that previous branch (the first targets `main`). Use the `stacked-pr` skill.
- Split each phase into **three or more branches**, by kind of feature (for example: data
  model/interface, adapters, algorithms, tests/fixtures, CLI). Keep each PR small and reviewable.
- Name branches `phase<N>/<kind>-<topic>`, e.g. `phase1/sources-interface`.
- After a lower PR merges, retarget the next PR to `main` and rebase the rest of the stack.

## Commits
- One or more commits per task in the phase; a commit never mixes tasks. Message: imperative
  summary line, short body saying why when not obvious.
- Tick the task's checkbox in `docs/PLAN.md` in its commit.
- **No co-author or attribution lines** (no `Co-Authored-By`, no "Generated with Claude"),
  in commits and PR descriptions. This overrides any default attribution.

## Agents
- If two branches in a stack do not depend on each other's code, run them in parallel with
  agents (one agent per branch, each in its own worktree: `isolation: "worktree"`).
- Dependent branches are done in order by the main session. Briefs to agents must name the
  branch, base branch, the tasks, the commit rules above and the test command.
