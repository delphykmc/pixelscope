# UX-3A — Measurement CSV export

Status: implementation slice tracked by GitHub Issue #153, parent #145; server result schema gate #140.

## Contract boundary

File > Export Result > Measurements (CSV)... is a user-requested export from an existing verified in-memory AnalysisResult. It is NOT portable Save Result As, a server artifact, an full-pair ROI metric, or a reloadable file. Open Result and Save Result As stay disabled without separately approved and installed H2 validated loader/writer (#140).

## CSV columns / scientific rules

All rows identify result, source A/B labels and image dimensions, Attribute ID/name/unit/quality direction and availability.

- FULL_PAIR_COMPARISON: one row per Attribute in original supplied order; value is exactly the adapter-supplied official full-pair scalar, not recomputed from the grid; no ROI metadata.
- GRID_DERIVED_ROI: additional row only when the currently selected original-pixel ROI and this Attribute's spatial grid exist; area-weighted grid mean, actual ROI x/y/width/height, valid area, total area and valid coverage. NEVER represents official ROI quality.
- Missing, failed, empty-valid-mask and unavailable numbers serialize as empty value, NOT zero. Actual numeric zero stays numeric. Partial official availability remains partial if a value is supplied.
- Source A/B identity and metric sign never change upon visual T/Alt+X pane swap. UI Map Gain and clipping never modify exported measurements. Original RGB paths need not exist.
- Standard Python csv.writer handles comma/newline quoting; CRLF records, UTF-8 BOM improve Windows Excel import. Untrusted labels and IDs are prefixed with apostrophe if they start with spreadsheet formula metacharacters. Numbers remain numeric.
- Same-directory temporary file and os.replace avoid partially written outputs; failed/cancelled export does not mutate source results.

## Test and owner acceptance

Tests: tests/enterprise/test_measurement_export.py (Qt-free scientific and file contract); tests/enterprise/test_analysis_ux3a.py (GUI action and error paths).

On Windows in the feature branch, use the following:

    git switch feat/153-enterprise-iqa-ux3a-csv-export
    git pull --ff-only
    $env:PYTHONPATH = "src"
    & $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_measurement_export.py tests/enterprise/test_analysis_ux3a.py tests/enterprise/test_analysis_window.py tests/enterprise/test_analysis_ux2c.py
    & $py -m pytest -q --deselect=tests/unit/test_issue121_iqa_reference_architecture.py::test_enterprise_reserved_paths_are_not_owned_by_main

Launch the standalone sample with python -m pixelscope_enterprise.iqa.demo --rgb, select a ROI and export CSV. Check full-pair vs grid-derived columns and preserved A/B source identity after swap. With ROI cleared, exported rows are official-only. Verify invalid/missing cells are not zero, cancellation is no-op and failure message is visible. Generic CI cannot replace these native Qt tests.

## Remaining UX-3 milestones

- UX-3B: separate image/Map PNG and standalone HTML reporting, preserving missing-source and signed/validity semantics.
- UX-3C: Enterprise extension job registry/status, completion notification and user-directed View Result action via public host contribution, synthetic first.
- UX-3D: genuine portable Open/Save As only AFTER #140 approved versioned, checksum/READY-validated, bounded manifest/NPZ schema and independent scientific/user state round-trip.
- UX-3E: normal-GC multimonitor/packaging acceptance and SHA/file manifest for user-approved PRIVATE SUB import.

Only Enterprise-owned paths may change; PR base must be handoff/enterprise-iqa-window. PUBLIC MAIN must never receive Enterprise files.

## Export menu structure and comparison with established applications

The user-facing menu is intentionally hierarchical, following image-analysis
applications that distinguish exporting **measurements**, **images** and
**reports**. ImageJ supports exporting measurements separately from image data;
QGIS uses Project > Import/Export > Map to Image/PDF; napari distinguishes
viewer screenshots from source layers. MATLAB offers image/figure export
formats via grouped export actions.

```text
File
  Open Result...                [H2 reader; disabled until verified]
  Save Result As...             [H2 portable result; disabled until verified]
  Export Result >
    Measurements (CSV)...       [UX-3A; implemented]
    Images (PNG)...             [UX-3B; add only when functional]
    Report (HTML)...            [UX-3B; add only when functional]
```

**Only** Measurements (CSV) is currently instantiated in the submenu; the
other lines are future menu targets, not disabled placeholder actions.

### User-facing terminology

Avoid the ambiguous word `OFFICIAL` in visible UI/CSV. Call the producer-
provided global scalar the **full-pair comparison**, and call the
area-weighted estimate on a user-defined rectangle the **grid-derived ROI
estimate**. CSV scope IDs are `FULL_PAIR_COMPARISON` and `GRID_DERIVED_ROI`.
The underlying model's `official_value` and `official_availability` field
names are preserved for binary/API compatibility; they are implementation
identifiers, never exported labels. A full-pair comparison is not a region
score. Image-level export and Save Result As remain separate.
