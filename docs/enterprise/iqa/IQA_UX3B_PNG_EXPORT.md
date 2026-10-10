# UX-3B (PNG) — Original-coordinate visual export

Status: implementation in a separate Handoff-only PR for #153/#145. Depends on
the merged U3/U11 nested layout and U5/U6 dock/composition changes from #156.
**Do not import into PRIVATE SUB** without independently frozen SHA/manifest review.

## Operator workflow

File > Export Result > **Images (PNG)...** exports *images*, not CSV
measurements, on-disk IQA result, or original sensor RAW content.

1. Open a verified `AnalysisResult` (synthetic public-safe demo is acceptable).
2. Optionally select an ROI using Shift+drag. When ROI exists, choose **Full
   image**, **Active ROI**, or **Both**. Without ROI, Full is used automatically.
3. Select an existing parent directory. The exporter creates a **new**
   `iqa-images-<sanitized-result-id>/` child folder; an existing destination is
   rejected rather than overwritten. Choose another parent/rename the existing
   result folder to export again.

Contents: `source_A_full.png`, `source_B_full.png`,
`selected_map_full.png`, optional corresponding `*_roi.png`, plus
`export_info.json`. Missing source A/B or missing selected Map yields no
placeholder PNG: omissions are recorded in JSON. At least one real visual layer
must exist. All files are staged and published together using a same-parent
directory rename; failures clean the staging folder. Cancel is a no-op.

### Scientific boundaries

- Original images are the **decoded RGB as loaded into AnalysisWindow**, at
  original pixel dimensions (PNG is *not* bit-exact RAW/high-bit-depth preservation).
  Export uses the logical A/B source identities, **not** the swapped pane order,
  GUI capture, zoom, overlays or Hotspot annotations.
- All exported layer rectangles use half-open original source-pixel bounds
  `[x, x+w) × [y, y+h)`. Drawn ROI bounds are integer-clipped as in current
  AnalysisWindow ROI handling; saved fractional user state uses floor/ceil.
- Selected Spatial Map is **only a display visualization** of the
  `AttributeDisplay.spatial` grid with cell-origin/step geometry, nearest-cell
  pixel-center sampling and transparent invalid/uncovered pixels. No interpolation
  claims new high-frequency measurement evidence. Selected unit's display
  `Range ±R` and Map `Gain ×G` determine the effective half-range `R/G`;
  these never alter the scientific arrays, CSV or official full-pair comparison.
- Signed unoriented metrics use neutral positive/negative colors; a qualitative
  A/B winner must not be inferred. `export_info.json` contains selected
  Attribute ID/label/unit, direction metadata, Range/Gain, valid and clipped
  **whole-grid cell counts** and explicitly tagged scope. ROI coverage and
  GRID-derived mean are descriptive only and separately labelled; they are
  **not regional producer-provided full-pair scores**.
- Missing source files, invalid grid cells, valid numeric zero, and selected
  missing Map are distinguishable; source absolute paths, server credentials,
  job/runtime state and source pixels are not recorded in JSON.
- Files are not loadable via `Open Result` / `Save Result As`. The portable
  verified reader/writer remains blocked by #140. HTML Report is separately
  scoped and not implemented in this PNG PR.
- Max per-image export is currently 16,777,216 source pixels, preventing
  accidental unbounded RGBA allocations for UHD+ cases. Higher-resolution
  streaming/tiled exports require an explicit separate design/review.

## Implementation ownership and tests

Production code: `src/pixelscope_enterprise/iqa/visual_export.py` and
a small action/GUI adapter in `analysis_window.py`. No MAIN-owned code, no
private symbols, no U4 generic registration hooks, no U6 settings changes.

Run from a Windows Python 3.10 checkout of the PR branch, preferably separate
processes for pure-model and native Qt tests:

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_visual_export.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_analysis_ux3b.py tests/enterprise/iqa/test_analysis_ux3a.py tests/enterprise/iqa/test_analysis_roi_chart_scope.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_dock_lifecycle.py tests/enterprise/iqa/test_iqa_composition.py
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
```

Visual owner review: run `python -m pixelscope_enterprise.iqa.demo --rgb`,
try Full/ROI/Both at FHD and UHD, change Attribute, Range and Gain, verify
source coordinate identity and transparent invalid cells in an external image
viewer, swap pane order and re-export, then test missing A/B, missing Map and
destination collision. Owner Windows Qt tests, independent review and change-
scoped CI must pass before merging **into Handoff only**.
