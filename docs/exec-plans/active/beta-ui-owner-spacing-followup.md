# Execution plan: Beta UI owner spacing follow-up

Status: Active
Owner: ChatGPT orchestrator with independent review
Branch/PR: `codex/beta-ui-hardening-pass2` / draft PR #68
Last updated: 2026-08-31

## Goal

Correct the owner-observed RAW Minimum Stride visibility and Plots header-height
regressions without changing RAW calculations, analysis results, responsive wrapping,
or the established constrained-workspace contract.

## Scope

### In scope

- Give the existing Minimum Stride label usable row width while retaining its zero
  horizontal floor and word wrapping.
- Remove unintended style-default margins inside the shared responsive Plots layout;
  outer Histogram and Line Profile panel padding remains authoritative.
- Add rendered-geometry regression tests and validate offscreen and Windows-native.

### Out of scope

- RAW parsing/profile semantics, Histogram or Line Profile calculations, new control
  presentation, dock lifecycle, and unrelated formatting.

## Current state

PR #68 owner comment `#issuecomment-5469909026` reports two presentation regressions.
Exact probes at head `e8ea641` found that `minimum_stride_value` had nonempty text but
a zero-pixel width while its trailing spacer consumed the row; height-for-width then
expanded the empty-looking row to 60 pixels. `ResponsiveControlLayout` inherited nine
style pixels at both top and bottom, producing a 40-pixel host for 22-pixel controls.
Existing tests covered logical text, wrapping, and state but not these geometries.

## Invariants and constraints

- CPython 3.10 x64 and existing Qt ownership remain unchanged.
- Minimum Stride keeps `minimumWidth = 0`, horizontal `Ignored`, and word wrapping so
  the RAW dialog does not regain a hard width floor.
- Responsive Plots remain single-row when content fits and reflow only when constrained.
- No analysis/request/result, dock, or persistence authority changes.

## Proposed design

Stretch the existing Minimum Stride label instead of a trailing spacer. Set the
custom responsive layout's internal margins explicitly to zero and retain its existing
spacing and height-for-width algorithm. Assert actual visible geometry rather than
only logical widget state.

## Implementation slices

1. **RAW diagnostic row**
   - Files/components: `raw_open_dialog.py`, component-resize tests.
   - Observable result: guidance is visible and the row contains no unexplained band.
   - Tests: default/update geometry plus existing RAW domain and scroll checks.
2. **Plots header chrome**
   - Files/components: `responsive_control_layout.py`, component-resize tests.
   - Observable result: wide headers equal live row height; narrow fallback is retained.
   - Tests: Histogram and Line Profile wide/narrow/state/context coverage.

## Validation plan

- Targeted offscreen and Windows-native component/RAW tests.
- Related Plots, analysis-request, reference, legend, and workflow regressions.
- Ruff check/format, mypy, documentation contract, pip and diff checks; full offscreen
  pytest before exact-head review.
- Owner Windows 100/125/150/200% presentation confirmation remains the final visual gate.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| RAW label restores width pressure | minimum-hint and constrained dialog tests | retain `Ignored` and zero minimum width |
| Plots wrap threshold or state regresses | existing wide/narrow state test | remove only internal margins; keep algorithm unchanged |
| Offscreen metrics differ from Windows | Windows-native focused run and owner DPI check | do not claim offscreen as visual qualification |

## Progress log

- 2026-08-31: owner findings read from PR #68 and independently analyzed at `sol/high`.
- 2026-08-31: deterministic root probes measured RAW label width 0 / row height 60 and
  Plots internal margins 9+9 / header height 40 for 22-pixel controls.
- 2026-08-31: narrow fixes and rendered-geometry coverage implemented. Focused
  Windows-native tests passed 14 in 3.13 seconds; related offscreen tests passed 46 in
  14.99 seconds.
- 2026-08-31: full offscreen pytest completed with 1078 passed, one Windows
  symlink-privilege skip, and the established Folder Display Tag/offscreen failure in
  375.40 seconds; the previously protected Bayer `Gr@1` node passed in this run.
  Changed-file Ruff/format, `mypy src` for 123 files, `pip check`, documentation
  contract/unit test, and diff checks passed. Commit/push and exact-head review remain
  pending.

## Completion summary

Pending validation, commit, push, and exact-head independent review.
