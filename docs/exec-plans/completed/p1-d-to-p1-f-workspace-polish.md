# Execution plan: P1-D to P1-F workspace polish

Status: Complete  
Owner: repository owner + coding agents  
Branch/PR: P1-D PR #10; P1-E PR #11; P1-F PR #12  
Last updated: 2026-08-07

## Goal

Complete primary-image ordering, atomic Split Channels transitions, Plots and
Statistics workspace polish, and removal of obsolete Multi View arrangement
compatibility state without combining unrelated risk in one PR.

## Completion state

| Phase | Result |
|---|---|
| P1-D | Merged as PR #10 |
| P1-E | Merged as PR #11 |
| P1-F | Merged as PR #12 at `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f` |

## Delivered behavior

### P1-D — Multi View ordering and Split transition polish

- Every regular two-to-six-image Multi View exposes primary-image behavior.
- Primary promotion changes display order only; Files order, logical document
  IDs, badges, viewer reuse, and synchronized ranges are preserved.
- Two/four/six layouts remain equal-sized; three/five enlarge the first tile.
- Split Channels replacement applies final geometry before binding replacement
  content, avoiding the old-grid intermediate frame.
- Page Up/Page Down folder-pair navigation remains an application shortcut.

### P1-E — Plots and Statistics workspace completion

- Floating Plots geometry and selected tab persist.
- Title-bar double-click and the explicit control share maximize/restore logic.
- Esc clears ROI; Shift+Esc clears Line Profile.
- Ctrl+drag creates ROI; Shift+drag creates Line Profile; Alt+drag creates neither.
- Statistics grouping, Active ROI lifecycle, bit-depth/Pixels display, label
  elision, separators, clipboard, and CSV contracts were completed.

### P1-F — fixed-layout compatibility cleanup

- Removed arrangement constants, registry, runtime fields, actions, setter,
  startup/save behavior, render calls, and six-source restore dependency.
- Startup ignores the legacy `ui/multiview_arrangement` key; save does not write
  it; Reset Workspace Layout removes it.
- `MultiCompareView._fixed_geometry()` is the sole one-to-six geometry policy.

## Preserved invariants

- Ordered selection remains the comparison model.
- Primary identity does not rewrite Files selection or logical IDs.
- Split component order remains fixed.
- Difference placement and exact six-source restoration remain stable.
- Plots persistence and workspace reset behavior remain stable.

## Validation evidence

The repository owner recorded that the full automated repository contract
passed for P1-D, P1-E, and P1-F: documentation checks, full pytest, Ruff lint and
format checks, mypy for `src`, and `pip check`.

P1-D and P1-E also have recorded manual Windows behavior checks. P1-F manual
Windows visual/timing checks were not re-verified during P2-0 and are not claimed
as passed here.

## Historical risks and mitigations

| Risk | Mitigation |
|---|---|
| Primary promotion mutates logical identity | Restrict changes to `_multi_display_order` and retain focused tests |
| Split replacement paints stale geometry | Apply final geometry first and batch content binding |
| Plots geometry restores incorrectly | Persist only valid floating geometry and test docked/floating states |
| Arrangement removal breaks restore | Merge P1-D/P1-E coverage first, then remove compatibility state |

## Progress log

- 2026-08-06: P1-D merged as PR #10.
- 2026-08-06: P1-E merged as PR #11.
- 2026-08-06: P1-F implementation and automated validation completed in PR #12.
- 2026-08-06: PR #12 merged at `1f13e85bccf3ef1eab7f27c87c84f798eadfcc2f`.
- 2026-08-07: Plan archived during P2-0; no runtime behavior changed.

## Completion summary

- Delivered behavior: workspace-polish program described above.
- Changed areas: Multi View, Split transition, Plots/Statistics workspace,
  settings cleanup, tests, and durable documentation.
- Validation: automated contract recorded as passed by the repository owner;
  P1-F manual Windows evidence not re-verified in P2-0.
- Remaining limitations: deferred work is tracked by the P2–P7 roadmap.
- Durable docs: this completed plan, `docs/CURRENT_STATE.md`,
  `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, and `docs/ROADMAP.md`.
