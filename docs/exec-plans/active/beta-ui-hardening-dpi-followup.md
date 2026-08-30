# Execution plan: Beta UI DPI command-row follow-up

Status: Active — accepted subset implemented and validated; exact-head review pending
Owner: ChatGPT orchestrator with independent review
Branch/PR: `codex/beta-ui-hardening-pass2` / draft PR #68
Source experiment: stacked draft PR #69 at `db52ad053dfca6ff35a4d741dd30b0022c292e86`
Last updated: 2026-08-30

## Goal

Integrate the owner-validated high-DPI Image command-row corrections prototyped in
PR #69 into PR #68 without merging the experimental stack or retaining a negative IQA
growth-policy experiment. Preserve normal-width presentation, constrained-workspace
acceptance, accessibility, and one presentation-hardening authority.

## Observable scope

- `Clear` and `Keep` are compact visible labels; complete `Clear Selection` and
  `Keep Selection` command meaning remains in accessible names and tooltips.
- Layout and Gain selectors retain their complete values and native drop-down chrome at
  their current font/style content floor, while accepting surplus width.
- Metric floors refresh after relevant font/style changes rather than freezing a startup
  snapshot.
- The final composed workspace continues to accept the bounded logical reference sizes;
  no resize-event allocator or second command-row authority is introduced.

## Explicit exclusions

- Drop PR #69's `RemoteIqaWorkspace` `Ignored → Preferred` experiment and its tests; owner
  Windows testing found no meaningful recovery improvement.
- Do not cherry-pick or merge PR #69 directly. Its nine owner commits remain untouched.
- Do not add a custom IQA dock allocator, numerical/IQA schema changes, Remote production
  integration, or unrelated formatting cleanup.

## Work and review sequence

1. Audit exact PR #69 base/head, follow-up guidance, product contracts, call sites, and
   affected tests.
2. Obtain independent `sol/high` accept/drop review.
3. Fold accepted behavior into `presentation_controls.py`; update focused tests and
   durable product/quality/UI wording.
4. Run focused offscreen and Windows-native checks, constrained-size/font-change probes,
   full pytest, static/docs gates, and base-to-head diff review.
5. Commit/push with explicit ChatGPT attribution, independently review the exact PR #68
   head, record PR #68/#69 disposition, then archive this plan.

## Progress log

- 2026-08-30: owner reported multi-monitor and dock validation successful, while 200%
  DPI validation exposed clipped Layout/Gain/Clear/Keep controls. PR #69 was provided as
  a stacked experiment with a Codex follow-up guide.
- 2026-08-30: exact audit confirmed PR #69 is based on PR #68 head `6b3e352`, contains
  five files and nine commits, and is intentionally not a replacement for PR #68.
- 2026-08-30: independent `sol/high` review requested corrections before integration:
  drop the ineffective IQA policy, fold command sizing into the existing presentation
  authority, refresh metrics dynamically, isolate settings, reconcile terminology, and
  assert real resize acceptance rather than only self-assigned child minima.
- 2026-08-30: accepted behavior was folded into `presentation_controls.py`; no PR #69
  production/test file was copied. Content floors now follow current Qt font/style metrics,
  refresh through one window-owned event-filter owner, and keep Page/count shrinkability.
  The IQA `Preferred` experiment is absent from PR #68.
- 2026-08-30: an offscreen-only implementation initially exposed a Windows-native 1 px
  Page boundary miss at 960 logical px. The Page floor now retains both zero-minimum
  eliding slots inside their host without making their text a new fixed floor.
- 2026-08-30: direct command-row/Review Selection tests passed 15 offscreen in 8.49
  seconds and 15 Windows-native in 10.54 seconds. The broader affected set passed 104
  tests in 53.92 seconds. Full offscreen pytest reported 1076 passed, one Windows
  symlink-privilege skip, and the same two established Folder Tag/Bayer failures in
  372.79 seconds. Changed-file Ruff/format, `mypy src` for 123 files, `pip check`, the
  documentation contract, and whitespace checks passed.

## Validation targets

- Focused command-row, Pass 2 workspace, Review Selection, workflow, and composition tests.
- Windows-native focused tests plus owner DPI confirmation where available.
- Full offscreen pytest with established exceptions reported, never hidden.
- Changed-file Ruff/format, `mypy src`, `pip check`, documentation contract, and
  whitespace/base-to-head semantic diff checks.

## Completion conditions

- PR #68 exact head passes independent review with no unanswered PR #69 follow-up item.
- PR #69 remains an unmerged experimental Draft and its negative IQA experiment is not
  present in PR #68.
- Remaining manual constraints and the actual commit/GitHub attribution method are
  recorded without claiming unobserved validation.
