---
name: stacked-pr
description: Create or maintain a stack of branches and stacked PRs for a FlowReel phase. Use when starting a phase, adding a branch to the stack, or after a lower PR merges.
---

# Stacked PRs

Follow `.claude/rules/git-workflow.md`.

1. List the phase's branches from `docs/PLAN.md` in dependency order.
2. Create the first branch from `main`, each next one from the previous branch:
   `git switch -c phaseN/<kind>-<topic> <previous>`.
3. Per task: implement, test, commit (one commit per task, checkbox ticked, no co-author line).
4. Push and open the PR with `gh pr create --base <previous branch or main>`. Description:
   what, why, the tasks done, how tested. No attribution line.
5. Independent branches (no shared code): spawn one agent per branch with `isolation: "worktree"`.
6. When a lower PR merges: `gh pr edit <next> --base main`, then
   `git rebase --onto main <old-base> <next>` up the stack and `git push --force-with-lease`.
7. Ask before merging any PR or force-pushing; never push to `main`.
