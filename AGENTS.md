# PixelScope Agent Guide

Use this file as a map. Read only the documents relevant to the task, then inspect the related source and tests before changing behavior.

## Start here

- Product intent and user-visible behavior: `docs/PRODUCT_SPEC.md`
- Architecture, boundaries, and lifecycle rules: `docs/ARCHITECTURE.md`
- Durable engineering decisions: `docs/DECISIONS.md`
- Current and future scope: `docs/ROADMAP.md`
- Packaging constraints: `docs/PACKAGING_CONSTRAINTS.md`
- Documentation map and maintenance rules: `docs/index.md`
- Long or multi-step work: create an execution plan from `docs/exec-plans/TEMPLATE.md`
- Required validation and completion evidence: `docs/QUALITY.md`

## Non-negotiable constraints

- Target CPython 3.10 x64. Do not use Python 3.11+ syntax or APIs.
- Keep PyInstaller fixed at exactly 5.7 `onedir`; do not install or run packaging tools unless explicitly requested.
- Keep numerical algorithms out of Qt widgets and expensive work off the UI thread.
- Preserve source dtype, channel meaning, strides, endianness, and image bounds explicitly.
- Promote operands before difference, squared-error, or other overflow-prone arithmetic.
- Do not change public behavior without inspecting related source, tests, product specification, and architecture notes.
- Add or update tests with every functional change.
- Do not preserve temporary integration scripts or workarounds as permanent architecture.
- Never log credentials, image content, or unnecessary sensitive paths.
- Do not modify files outside this repository or perform destructive Git operations.

## Working method

1. Restate the task as observable behavior and explicit scope exclusions.
2. Read the smallest relevant document set from `docs/index.md`.
3. Inspect implementation, call sites, and tests before editing.
4. For work spanning multiple components or sessions, create and maintain an execution plan.
5. Prefer small, reviewable changes with explicit invariants over broad rewrites.
6. Run the checks in `docs/QUALITY.md`; report exact commands, results, and any unavailable checks.
7. Update durable docs when architecture, product behavior, constraints, or decisions change.

Final reports must list changed files, validation commands and results, manual checks, and known constraints.
