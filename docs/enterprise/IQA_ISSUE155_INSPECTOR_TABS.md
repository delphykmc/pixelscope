# Issue #155 — Inspector compact tabs (Slice A)

Scope: Enterprise-only `AnalysisWindow` Inspector layout refactor. Based on approved
UX-3A Handoff merge `00f5005db44e22767233ed2a3dd2a64e6500fa0e`.

## Operator issue

The old vertical two-way `inspector_splitter` permanently allocated height to
both a long Attribute chart and three tall analysis cards. At 1366×768 and
other sub-FHD heights the chart lost useful scan area even when Details
were not relevant. Moving a splitter handle could not eliminate its
non-collapsible minimums.

## Slice A — implemented in the first PR

- Right Inspector has an always-visible one-line source ROI identity
  `ROI: (x, y) · W×H px` and enabled `Clear` action when a ROI exists.
  Full source geometry and coverage remain available on **Details**.
- `QTabWidget` with **Attributes** (default, full height for unit-group
  numeric bar charts and existing Range controls) and **Details**
  (scrollable Full-pair Comparison, ROI grid estimate and Map cells).
  The inactive tab does not consume any minimum vertical height.
- Plot numeric values, selected Attribute, ROI, Range per unit, Map Gain,
  source A/B presentation, Top-3, Bottom Hotspots Dock, QSettings window
  geometry and CSV export semantics are unchanged.
- Clicking Attributes / Details does not change analytical scope. The
  whole-pair comparisons remain whole-pair values, including while ROI
  is selected. This avoids any accidental quality direction inference.
- Stable Qt ownership: `self.inspector_tabs`, `self.group_scroll` and
  `self.details_scroll` remain owned widgets. No surrogate hidden splitter
  is kept.

### Owner Windows acceptance

```powershell
git switch feat/155-enterprise-inspector-tabs
git pull --ff-only
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/test_analysis_ux1.py `
  tests/enterprise/test_analysis_ux2c.py `
  tests/enterprise/test_analysis_window.py `
  tests/enterprise/test_analysis_ux3a.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -m pixelscope_enterprise.iqa.demo --rgb
```

Manual: inspect 1366×768 (or similarly short resolution) and FHD. Observe
Attributes chart fills all available right-panel height under compact ROI
header even when bottom Hotspots Dock is shown; Details tab scrolls through
full-pair, ROI and Map cards. Create ROI while in Details, return to
Attributes: chart is **still the original full-pair chart**, ROI badge
updates and Clear works without changing A/B or current Attribute.
Resize window and switch results.

CI runs only generic static/docs/tests by project policy; dedicated
Windows PySide6 UI acceptance must be performed by owner. Normal cyclic-GC
and external packaging validation remain downstream gates.

## Slice B — separate review PR, **not started**

Add a **visible** measurement Scope selector
`Full pair` / `Active ROI · GRID` matching MAIN Statistics' explicit
Full image / Active ROI UX. In ROI scope, charts show weighted
`roi_statistics` values, labelled provisional GRID-derived estimates
with unavailable/no-map/zero distinguished and neutral-quality semantics
unless producer-specific regional direction is verified. Range remains
visual, Map Gain changes colors only. Preserve state per Result,
migration of prior analysis_state and user-driven scope transitions.

Slice B must not silently reclassify local Grid means as verified quality,
modify `FULL_PAIR_COMPARISON` export values, introduce private schema or
modify PUBLIC MAIN. Begin only after Slice A review/owner acceptance and
squash merge into `handoff/enterprise-iqa-window`.

## Safety boundary

No UX-3B PNG/HTML report work here. PRIVATE SUB server/model transport and
PUBLIC MAIN edits are out of scope. Preserve branch provenance and
security-controlled source migration.
