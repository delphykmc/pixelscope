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
  **No quality direction** (dark gray `#5E6873`, matching request 4).
  Untrusted or below-threshold values ->
  **Not visible**, drawn light gray at reduced opacity. Mask-invalid cells
  remain transparent regardless of policy.
- In conjunction with request 3 (#195), the Top-3 first-insight ranker skips
  un-oriented metrics; quality mode also skips explicit `quality_direction=none`.
  Direction-known metrics with an untrusted signal gate may still appear muted,
  with no claim of a quality verdict. The complete chart/map retain all metrics.
- The verdict is about the supplied **difference in its declared direction**,
  not an A/B positional preference and not an independent scientific score.
  GRID-derived ROI/hotspot colors are explicitly provisional local evidence,
  not an official ROI quality winner.
- Exploratory hotspots (`mode=exploratory_abs`) have no aligned official sign.
  In quality mode their cards are **muted** and read **Exploratory · No verified
  verdict** even if the local raw mean is positive/negative; they never assert
  Superior/Inferior. Aligned GRID candidates still carry only provisional color
  evidence, not verified local ROI quality.

## Integrated handoff contracts (requests 1, 2, 3 and 4)

- **Request 1 / #200:** The optional grayscale reference-A underlay owns the
  window toggle, image cache, and map-compositing path. The integrated
  `_map_pixmap` selects `quality_spatial_rgba` **or** legacy
  `colorize_spatial_rgba` once, then calls the common
  `apply_spatial_reference_tint_rgba` helper **exactly once** when the
  reference underlay is on. The quality helper also supports a standalone
  `translucent=True` option, but the window does not combine both attenuation
  paths. Exact zero and invalid cells have zero alpha; nonzero
  below-threshold/untrusted values have faint gray alpha; visible colors are
  capped at alpha 176. With no underlay, the quality-map alpha remains as before.
- **Request 4 / #198:** Visible neutral pixels/cards/bars reuse
  `NEUTRAL_PRESENTATION_RGB=(94,104,115)` / `#5E6873`; the quality-mode
  neutral chart track is `#E1E5E9`. The lighter muted gray (`#D3D6DB`)
  stays distinct.
- **Request 6 / #201:** The trusted-gate contract remains `True` only; `None`
  stays unknown without guessing source-original levels. Attribute-row tooltip
  explanations remain owned by #201.

The four integrated requests have focused combined Qt coverage. The remaining
three requests still require coordinated integration; these checks are not
a substitute for native Windows visual acceptance or permission to merge
individual branches independently.

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
