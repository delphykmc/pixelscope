# Execution plan: Beta UI hardening pass 2

Status: Active
Owner: ChatGPT orchestrator with independent implementation review  
Branch/PR: `codex/beta-ui-hardening-pass2` / draft PR pending  
Last updated: 2026-08-29

## Goal

Harden PixelScope's local desktop presentation so the complete Files + Image + IQA
workspace can be resized inside one FHD monitor at 100% scaling, while retaining useful
headroom for higher-DPI logical work areas. Completion is observed through production-
composed resize tests, populated/stress IQA inspection, focused and full repository
validation, before/after captures where the environment can render them, and independent
exact-head review. Remote IQA production-server integration is excluded.

## Scope

### In scope

- remove production-composed minimum-size accumulation from the Image command surface,
  IQA shell, Plots pages, status bar, RAW dialog, and Settings dialog;
- preserve access to existing commands and full long-text values through compact labels,
  eliding/wrapping, tooltips, scrolling, and Qt layout policy;
- keep IQA small/normal data readable and bound stress-result presentation work without
  changing server-authored measurements or result schemas;
- add observable resize/readability regressions and update the durable Beta UI contract;
- record automated evidence separately from owner-only Windows/DPI/multi-monitor checks.

### Out of scope

- Remote IQA production server, GPU, SMB, SSO/authentication, request/API/result-schema,
  P5 preflight, measurement, or numerical-contract changes;
- new docking/splitter/geometry state authorities or a new visualization framework;
- the two protected pre-existing pytest exceptions named by the owner;
- unrelated formatting, lint, packaging, or numerical cleanup.

## Current state

PR #67 merged as `main@0ccb8b867d4989fc87ca73a66ffe5b78a5239fa5` from
`033b6ba0289ed2b4eee13daaa73f9037a67a8da5`. It reduced the Current Pair A/B row and
explicit local width floors, but its final seven-file RGB8 contract correction was not
followed by recorded exact-head independent review or owner-local validation.

The Pass 2 offscreen production probe uses the real composition in
`pixelscope.app.application._compose_main_window_presentation`. Absolute widths are not
Windows qualification because this environment has no installed Qt font families, but
the structural behavior is reproducible: the main minimum hint is 1587 px without IQA
and 2127 px with IQA, and a 1280 px resize request remains 2127 px. The dominant hints
come from the one-row Image presentation controls (1301 px) and the composed
`RemoteIqaWorkspace` dock shell (534 px), which Pass 1 did not relax.

### Initial audit findings

- **P0:** none.
- **P1 — Main/FHD workspace:** Image command groups and the outer IQA shell accumulate
  intrinsic hints, so Files + Image + IQA can exceed FHD. Expected: required actions and
  status remain accessible while the production-composed window accepts a normal FHD
  resize. Risk: Page, Pick/Keep, Display Gain, P5-D Inspect/Return, and alias controls
  must keep their existing authorities.
- **P1 — Plots:** the inactive Line Profile page establishes the whole dock width through
  one long controls/status row. Expected: Histogram and Line Profile both yield without
  hiding their controls. Risk: mode/channel/reference and empty-state behavior remain
  unchanged.
- **P1 — RAW dialog:** a 280 px fixed width conflicts with a larger layout hint and the
  unscrolled vertical body. Expected: controls and diagnostics remain reachable on
  constrained/high-DPI work areas. RAW validation/decode semantics are unchanged.
- **P1 — Settings dialog:** the hard 820x540 minimum can exceed the logical work area of
  an FHD monitor at elevated scaling even though pages already scroll. Expected: footer
  actions remain reachable and all categories remain usable.
- **P1 — IQA stress presentation:** a valid 32-attribute, 16-variant, 128-scene model
  synchronously created 512 curves, 4,128 tree rows, and roughly 43,400 characters of
  hover text per Scene in about 7.5 seconds. Expected: Beta users can identify/filter
  series and inspect details without eager expansion of every collapsed row or unbounded
  default series. Server measurements and canonical comparison math remain unchanged.
- **P2 — Status bar:** long filenames and multi-image pixel summaries affect the row's
  intrinsic width and may clip without complete tooltip coverage. Expected: bounded,
  prioritized display with full text retained for tooltip/accessibility.
- **Observation:** Qt-native Files collapse, Image non-collapse, IQA detail splitters,
  bottom-corner ownership, tile filename eliding, and Statistics summary eliding already
  follow the desired ownership model and should be preserved.

The three PR #67 carried nodes were re-run together on this baseline in the current
offscreen environment and passed (`3 passed in 2.43s`), including the previously noted
Difference numeric shortcut. This does not erase the owner's protected known-exception
policy for environments where the first two reproduce.

## Invariants and constraints

- Target CPython 3.10 x64 and the existing PySide6/pyqtgraph stack.
- Qt remains the sole dock, splitter, and window-geometry authority.
- Existing Files/Selected/current-page, Primary, Difference, Display Gain, IQA Reference,
  result, submission, Inspect/Return, and persistence authorities are unchanged.
- Full long text remains available through tooltip/accessibility when presentation is
  compacted; information is not silently discarded.
- No production Remote IQA connection is used.
- Windows DPI and multi-monitor behavior is never inferred from offscreen Qt.

## Proposed design

Use one presentation-hardening layer to assign shrinkable policies to the final composed
widgets, not only their pre-composition placeholders. Bound one-row command surfaces with
short visual labels/icon controls plus full accessible names/tooltips. Move secondary
status text to shrinkable/wrapping rows where necessary. Keep plot/result math and state
in existing controllers.

For IQA stress data, keep attribute/variant/scene identities intact while lazily creating
collapsed hierarchy children and bounding the initial Scene Trend selection. The existing
attribute checklist remains the user-owned filter and can reveal additional series on
demand. Hover content describes only currently visible series.

Dialogs retain their existing models and validation; only size policy, scrolling, and
layout composition change. Status values retain full logical text while rendering an
elided form inside allocated space.

## Implementation slices

1. **Global workspace and compact command surfaces**
   - Files/components: Beta hardening, Image controls, Plots controls, status bar.
   - Observable result: production-composed hidden/visible-IQA and Plots states resize
     inside FHD; commands and full long values remain accessible.
   - Tests: production-composed resize and long-text/status regressions.
2. **Dialog readiness**
   - Files/components: RAW and Settings dialogs.
   - Observable result: dialogs yield to constrained work areas without clipped actions.
   - Tests: size-policy, reachability, and representative page/content regressions.
3. **IQA populated/stress readability**
   - Files/components: IQA result workspace and focused tests/capture fixture.
   - Observable result: small/normal behavior is preserved; stress data starts with a
     bounded readable series set and lazily materializes detail rows.
   - Tests: small/normal/stress model counts, filtering, hover bounds, and selection.
4. **Durable docs and closeout**
   - Files/components: Beta UI note, current state as appropriate, this plan.
   - Observable result: exact delivered behavior, evidence, limitations, and owner manual
     checklist are current and reviewable.
   - Tests: docs check, diff deletion/stat review, standard repository gates.

## Validation plan

- Focused: affected UI modules plus PR #67 Beta/IQA regression suites.
- Production probes: 1280x720, 1366x768, and 1920x1080; empty/populated; IQA hidden,
  docked, and floating; Plots Histogram/Line Profile current and inactive.
- IQA: synthetic small, normal, and stress results; before/after captures with identical
  data and viewport where the offscreen renderer is usable.
- Full checks: pytest, Ruff check/format check on the repository without unrelated fixes,
  mypy, pip check, docs check, and diff check.
- Manual Windows owner checks: 100/125/150/200%, multi-monitor and mixed-DPI movement,
  dock/float/maximize/restore/drop, restart geometry, workspace reset, long names/tags,
  1/2/4/6 Image, populated/stress IQA, toolbar/menu visibility synchronization.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| compact controls hide required actions | accessibility/visibility tests and captures | keep every action present; use short visual text with full tooltip/name |
| new layout becomes another geometry authority | code review and dock/splitter regressions | change hints/policies only; no resize-event allocation controller |
| IQA filtering changes numerical meaning | model/result regression suites | filter presentation only; reuse existing explorer statistics and checklist |
| lazy tree breaks selection/Inspect | focused hierarchy and P5-D tests | preserve item data and materialize selected/expanded attribute children |
| offscreen evidence is mistaken for Windows PASS | PR matrix/manual checklist | label all Windows/DPI/multi-monitor checks as owner-required |

## Progress log

- 2026-08-29: PR #67 and exact merged baseline audited; no open review threads, but a
  final-head review/validation evidence gap was recorded.
- 2026-08-29: production-composed empty/populated captures and 38 focused PR #67 tests
  completed; 38 passed in 14.65 seconds.
- 2026-08-29: initial global/IQA audits classified; no product/contract decision blocker
  was found. Remote production integration remains excluded.
- 2026-08-30: package commits completed for workspace minimum-size hardening
  (`f69a26f`), compact components/dialogs (`d245e6b`), and IQA stress readability
  (`0aa5fe0`).
- 2026-08-30: integrated focused validation passed 114 tests in 64.06 seconds. The
  production FHD long-name probe accepted 1920 x 1080 with IQA hidden and docked; the
  docked minimum hint was 985 px in the fontless offscreen environment.
- 2026-08-30: identical existing review captures were generated before/after. Additional
  1280 x 720 IQA small/normal/stress captures succeeded; stress presentation completed
  in 0.600 seconds with 32 visible series and 128 materialized Scene rows. This elapsed
  observation is not a test gate, and missing Qt fonts prevent Windows visual PASS.
- 2026-08-30: full offscreen pytest completed with 1058 passed, one Windows
  directory-symlink privilege skip, and two failures in 348.64 seconds. The protected
  Bayer `Gr@1` failure reproduced. The Folder Display Tag/elided-header node also failed
  unchanged on exact base `main@0ccb8b8` under the same environment, establishing it as
  pre-existing offscreen debt rather than a Pass 2 regression.
- 2026-08-30: `mypy src` passed for 122 files, `pip check` passed, and the documentation
  contract passed. Changed-file Ruff check/format passed. Repository-wide Ruff remains
  non-clean only for two unrelated import-order findings and 28 unrelated format-drift
  files; no unrelated cleanup was performed.

## Completion summary

- Delivered behavior: production-composed workspace, Plots/status/dialogs, and IQA stress
  presentation hardening implemented; independent review pending.
- Changed files: implementation/tests/docs are recorded in the branch diff; final list
  pending closeout.
- Validation results: focused 114 PASS; full pytest 1058 PASS / 1 SKIP / 2 proven
  pre-existing failures; static/docs checks as recorded above; independent review pending.
- Remaining limitations: owner Windows/DPI/multi-monitor qualification required.
- Follow-up issues: pending.
- Durable docs updated: this execution plan and `docs/ui/beta_workspace_hardening.md`;
  review closeout pending.
