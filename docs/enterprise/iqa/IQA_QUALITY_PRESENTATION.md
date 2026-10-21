# Optional IQA quality-verdict colors (handoff request 2)

Status: public-safe presentation option; downstream adapter must provide trusted
per-attribute metadata. Does not change scientific values, algorithms or exports.

## Final local acceptance correction (2026-10-21)

The owner's final acceptance request explicitly fixes Dark Neutral to RGB
`(94, 94, 94)` / `#5E5E5E`. This supersedes the original PR #198 blue-gray
`(94, 104, 115)` palette. The shared map/chart/card constant and exact RGB
regressions now follow that requirement. Scientific values, valid masks, ROI
statistics and export schemas remain unchanged; neutral visual PNG pixels use
the corrected shared palette. Quality toggling still does not change exports.

## Interpretation and controls

- Without host configuration, `View > Color by Quality Verdict` and
  `Tint Map over Reference` remain **off by default**. The PRIVATE Enterprise
  contribution can declare initial display defaults without mutating raw model
  results. The legacy red/blue palette is signed polarity only (positive/
  negative), **not** an A/B winner or per-attribute quality interpretation.
  Both chart endpoints use `− / +`; Top-3 labels say positive/negative signed.
  Opt-in Quality mode remains the only source of Superior/Inferior verdicts.
- When enabled, the sign of the **supplied** official or spatial difference
  remains unchanged. `AttributeDisplay.quality_direction` is an independent
  optional metadata field: `higher_is_better`, `lower_is_better`, or `none`
  (default). The UI must never guess this field from a metric label or from
  `quality_oriented`. The private adapter may attach verified directions for its
  own 14 attributes; the public demo attaches only synthetic directions.
- A trusted `summary_signal_gate is True` is required for a visible **dB** verdict.
  For dB, `None` (unknown) and `False` both mean **not visible**; signal validity
  cannot be inferred from a signed delta or map. Non-dB whole-image metrics
  (e.g. `color`) have no original-signal gate by design, so `None` must not
  suppress their eligible direction-aware verdict.
- An absolute signed difference **`>= 0.5` is visible, including exactly 0.5**.
  Differences strictly below the configured threshold are muted, and zero
  remains a non-difference even when the threshold is set to zero. The
  setting can be changed through `View > Set Visibility Threshold...`.
  This threshold is in the supplied attribute's units, applied to its own
  values; it is never a normalization or change to `fixed_range`.
- Visible, higher-is-better positive / lower-is-better negative -> **Superior**
  (blue `#3A6FD8`). The opposite signs -> **Inferior** (red `#C0392B`). Direction `none` ->
  **No quality direction** (dark gray `#5E5E5E`, matching request 4).
  Untrusted or below-threshold values ->
  **Not visible**, drawn light gray at reduced opacity. Mask-invalid cells
  remain transparent regardless of policy.
- In conjunction with request 3 (#195), the Top-3 first-insight ranker skips
  un-oriented metrics; quality mode also skips explicit `quality_direction=none`.
  In Quality mode, only visible, trusted, above-or-equal-threshold dB
  differences enter the ranked cards. Unknown-gate or faint candidates are
  **omitted**, not shown as muted Top-3 entries. The complete chart/map still
  present all available attributes with truthful individual display policy.
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

- **Request 1 / #200:** The optional grayscale role-designated **Reference**
  underlay owns the window toggle, image cache, and map-compositing path.
  If B is explicitly Reference, B is used; where no roles are supplied,
  legacy A is the Reference. A/B visual pane swapping never changes this. The integrated
  `_map_pixmap` selects `quality_spatial_rgba` **or** legacy
  `colorize_spatial_rgba` once, then calls the common
  `apply_spatial_reference_tint_rgba` helper **exactly once** when the
  reference underlay is on. The quality helper also supports a standalone
  `translucent=True` option, but the window does not combine both attenuation
  paths. Exact zero and invalid cells have zero alpha; nonzero
  below-threshold/untrusted values have faint gray alpha; visible colors are
  capped at alpha 176. With no underlay, the quality-map alpha remains as before.
- **Request 4 / #198:** Visible neutral pixels/cards/bars reuse
  `NEUTRAL_PRESENTATION_RGB=(94,94,94)` / `#5E5E5E`; the quality-mode
  neutral chart track is `#E1E5E9`. The lighter muted gray (`#D3D6DB`)
  stays distinct.
- **Request 6 / #201:** The dB trusted-gate contract remains `True` only;
  `None` stays unknown without guessing source-original levels. Attribute-row tooltip
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


## Official PRIVATE contribution startup defaults (2026-10-21)

The host may pass public-safe `IqaPresentationDefaults` through the documented
`IqaWindowContribution` constructor to `AnalysisWindowManager` and
`AnalysisWindow`:

```python
from pixelscope_enterprise.iqa.analysis_window import IqaPresentationDefaults
from pixelscope_enterprise.iqa.composition import IqaWindowContribution

contribution = IqaWindowContribution(
    # Existing PRIVATE load/save/job/settings callbacks remain unchanged.
    presentation_defaults=IqaPresentationDefaults(
        quality_enabled=True,
        tint_reference_enabled=True,
        visibility_threshold=0.5,
    ),
)
```

These are **initial window UI defaults**, not producer/model/server settings or
a change to PRIVATE Reader/Writer. Users may still toggle either View action or
change the threshold. The defaults are applied at actual window creation, before
a result is first rendered; manager window reopen behavior is unchanged.
When the role-designated Reference image is absent, Tint remains checked as a
preference but its action is disabled and the Map does **not** infer another
source. With no injected defaults the historical off-state is retained, but
its **labels no longer assert an A/B winner**. Do not infer a quality verdict
from `quality_oriented`, native producer sign or source role alone.

The PRIVATE owner reports its native signed difference follows a
Target-minus-Reference contract. Quality direction remains **per attribute**
and must be explicitly supplied by the trusted PRIVATE adapter; this public
Handoff does not globally reverse signs or rewrite exports.
