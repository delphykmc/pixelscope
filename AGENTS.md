# PixelScope Agent Guide

Use this file as a map, not a complete manual. Start from the current repository
state, read only the documents relevant to the task, then inspect the related
source and tests before changing behavior.

## Start here

- Current implementation and verified backlog: `docs/CURRENT_STATE.md`
- Documentation ownership and task-based reading paths: `docs/index.md`
- Product behavior: `docs/PRODUCT_SPEC.md`
- Architecture and lifecycle invariants: `docs/ARCHITECTURE.md`
- Durable engineering decisions: `docs/DECISIONS.md`
- Phase-level scope: `docs/ROADMAP.md`
- Validation and completion evidence: `docs/QUALITY.md`
- Packaging constraints: `docs/PACKAGING_CONSTRAINTS.md`
- Long or multi-session work: `docs/exec-plans/TEMPLATE.md`

## Non-negotiable constraints

- Target CPython 3.10 x64. Do not use Python 3.11+ syntax or APIs.
- Keep PyInstaller fixed at exactly 5.7 `onedir`; do not install or run
  packaging tools unless explicitly requested.
- Keep numerical algorithms out of Qt widgets and expensive work off the UI
  thread.
- Preserve source dtype, channel meaning, strides, endianness, bit alignment,
  and image bounds explicitly.
- Promote operands before difference, squared-error, or other overflow-prone
  arithmetic.
- Inspect related source, call sites, tests, product behavior, and architecture
  notes before changing public behavior.
- Add or update tests with every functional change.
- Do not preserve temporary integration scripts, compatibility bridges, or
  workarounds as permanent architecture without a recorded decision.
- Never log credentials, image content, or unnecessary sensitive paths.
- Do not modify files outside this repository or perform destructive Git
  operations.

## Working method

1. Express the task as observable behavior and explicit scope exclusions.
2. Read `docs/CURRENT_STATE.md`, then the smallest relevant document set from
   `docs/index.md`.
3. Inspect implementation, call sites, and tests before editing.
4. For work spanning components, multiple commits, or sessions, create and
   maintain an execution plan.
5. Prefer small, reviewable slices with explicit invariants over broad rewrites.
6. Run the checks in `docs/QUALITY.md`; run `scripts/check_docs.py` whenever
   Markdown or repository guidance changes.
7. Update durable docs in the same PR when behavior, architecture, constraints,
   decisions, or backlog state changes.
8. Report only validation output that was actually observed.

Final reports must list changed files, observable behavior, validation commands
and exact results, manual checks, known constraints, and deferred work.
