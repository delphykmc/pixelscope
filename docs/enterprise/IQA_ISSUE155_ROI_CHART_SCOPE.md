# Issue #155 — Slice B: explicit full-pair / ROI GRID chart scope

Status: implementation PR after Slice A #157 (squash-merged to Handoff at
`7fc609d9fca1866298066ec84e62c3b03cf6c904`).

## Semantics and provenance

IQA Analysis Window > right Inspector > CHART SCOPE is always explicit:

- **Full pair** is the default for new sessions and all legacy saved analysis
  states. It renders unchanged full-pair producer values, quality-oriented bar
  colors only where `AttributeDisplay.quality_oriented` allows them, and
  retains the existing quality-guarded Top-3 full-pair summary. It is
  completely unaffected by drawing or moving an ROI while selected.
- **Active ROI · GRID** is enabled when a real source-coordinate ROI exists.
  Each Attribute row displays its `roi_statistics(grid, roi).mean` (raw
  signed, area-weighted masked grid mean) with valid coverage. No grid or no
  valid selected cells -> **GRID MISSING**, no fabricated zero. A genuine grid
  mean of zero is `0.0`. Its badge, column heading, tooltip and legend
  explicitly state this is a **GRID-derived ROI estimate**, **not a verified
  local quality winner**, even for an Attribute whose full-pair comparison
  is quality-oriented. The delegate renders ROI polarity purple/teal,
  not full-pair red/blue.
- **First ROI selection** may automatically activate GRID-derived ROI mode
  only when the user has not manually overridden scope for that Result.
  Once the user explicitly selects Full pair, later Shift+drag cannot silently
  change to GRID; manual ROI scope remains available. Clear ROI restores
  Full pair and disables ROI selection.
- The ROI is always stored and drawn independently of chart scope. Source
  swap never changes ROI coordinates, source identity, signed value or
  underlying scientific payload.
- Display **Range ±R** remains per-unit symmetric *visual scaling only*.
  Map Gain changes only the map color/legend, not any displayed measurement,
  table value or CSV value. Attribute ranking/Top-3 stays globally scoped;
  ROI values are never ranked or presented as quality winners.
- CSV export (UX-3A) remains unchanged and independent of what is shown in
  the chart: `FULL_PAIR_COMPARISON` rows plus optional
  `GRID_DERIVED_ROI` rows for the selected spatial geometry.

## State contract

New `current_analysis_state` adds `chart_scope` (`full_pair` or
`roi_grid`) and `scope_user_override` (boolean). These are **user-only**
state, not producer/science data. The existing `analysis_state` validator
accepts (1) legacy H1 attribute-based ranges without gain, (2) H2 unit ranges
with gain, and (3) exact current fields with gain+scope. Older states
default to Full pair, including if their saved ROI exists; they never
silently reinterpret historical output as GRID-derived.

A saved `roi_grid` without a valid ROI, unknown scope, wrong override type,
invalid range, viewport or source dimensions is rejected *before any visible
state change*. Per-result scope is independent of other opened Results.

## Owner Windows acceptance

```powershell
git switch feat/155-enterprise-roi-chart-scope
git pull --ff-only
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/test_analysis_roi_chart_scope.py `
  tests/enterprise/test_analysis_window.py `
  tests/enterprise/test_analysis_ux1.py `
  tests/enterprise/test_analysis_ux2c.py `
  tests/enterprise/test_analysis_ux3a.py `
  tests/enterprise/test_measurement_export.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -m pixelscope_enterprise.iqa.demo --rgb
```

Manual in 1366×768 and FHD: Full pair/ROI GRID combo; select ROI on
A/Map/B, move selection, switch Full pair manually then drag again; verify
the mode stays Full pair until operator changes it. Switch Results and tabs,
adjust Range and Map Gain, export CSV, clear ROI, swap A/B presentation and
confirm no local A/B-quality winner inference. Test zero-valued grid and
missing/no-map Attribute, plus chart scroll and Qt native lifecycle.

Generic public CI intentionally cannot validate Enterprise PySide6 UI,
so owner Windows focused tests and an independent reviewer are required
before Handoff-only squash merge.

## Security boundary

Only Enterprise-owned downstream paths are modified. Not PUBLIC MAIN,
not UX-3B PNG/HTML, not #140 producer/portable file schema, not PRIVATE SUB
direct deployment. Preserve exact approved Handoff merge SHA for traceability.
