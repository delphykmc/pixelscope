# Optional IQA quality-verdict colors (handoff request 2)

Status: public-safe presentation option; downstream adapter must provide trusted
per-attribute metadata. Does not change scientific values, algorithms or exports.

## Interpretation and controls

- `View > Color by Quality Verdict` is **off by default**. Off retains the
  existing red A-better / blue B-better, neutral signed palette and Top 3 gate.
- When enabled, the sign of the **supplied** official or spatial difference
  remains unchanged. `AttributeDisplay.quality_direction` is an independent
  optional metadata field: `higher_is_better`, `lower_is_better`, or `none`
  (default). The UI must never guess this field from a metric label or from
  `quality_oriented`. The private adapter may attach verified directions for its
  own 14 attributes; the public demo attaches only synthetic directions.
- A trusted `summary_signal_gate is True` is required for any visible verdict.
  `None` (unknown) and `False` are both **not visible**. The existing signal gate
  is about original-relative signal evidence; it must not be inferred from a
  signed delta or local map.
- An absolute signed difference `<= 0.5` is **not visible** (inclusive); the
  setting can be changed through `View > Set Visibility Threshold...`.
  This threshold is in the supplied attribute's units, applied to its own
  values; it is never a normalization or change to `fixed_range`.
- Visible, higher-is-better positive / lower-is-better negative -> **Superior**
  (blue). The opposite signs -> **Inferior** (red). Direction `none` ->
  **No quality direction** (gray). Untrusted or below-threshold values ->
  **Not visible**, drawn light gray at reduced opacity. Mask-invalid cells
  remain transparent regardless of policy.
- The verdict is about the supplied **difference in its declared direction**,
  not an A/B positional preference and not an independent scientific score.
  GRID-derived ROI/hotspot colors are explicitly provisional local evidence,
  not an official ROI quality winner.

## Scope and invariants

- Only the on-screen chart bar, first-insight cards, relative spatial map,
  and local hotspot cards receive the optional policy. The optional legend and
  official detail string explain it. Existing source A/B/Map viewport position,
  ROI, selection, ranges, hotspot proposal rank, and numerical values do not
  change when the policy is toggled.
- The official-value model, spatial `values` and `valid_mask`, area-weighted
  ROI statistics, clipping counts, CSV, PNG/HTML report content and saved
  result/analysis-state schemas retain the existing semantics. Export routines
  still invoke the unchanged legacy `colorize_spatial_rgba` helper.
- Existing callers need not set new metadata. In quality mode, absent
  directions/gates safely display as gray rather than fabricating a verdict.
- Review via Qt-free `test_quality_presentation.py`, Qt
  `test_quality_presentation_window.py`, and owner Windows Python 3.10 /
  PySide6 6.4.2 functional/visual acceptance before import into private SUB.

**Handoff boundary:** these files remain on the temporary public handoff
branch; do not merge any `pixelscope_enterprise` path into public `main`.
