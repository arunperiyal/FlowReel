# Documentation guidelines

- Every public module, class and function has a docstring: what it does, arguments, return,
  units and coordinate conventions for fields. Keep them short.
- User-facing documentation lives in `docs/`; the design stays in `docs/PLAN.md`.
- A feature is not done until its docs are updated in the same PR: command help text,
  YAML option reference, and an example under `examples/` using generated data.
- Examples must run from a clean checkout without private data, logos or licensed music.
- Write plain, direct English; explain the why of a design choice, not only the what.
- Document YAML keys with type, default and an example. Keep names identical to the code.
- Note the physical meaning and sign convention of every derived field (vorticity, Q,
  lambda2, wall shear, forces).
- Phase 7 produces the tutorial; until then, keep a running `docs/` page per finished phase.
