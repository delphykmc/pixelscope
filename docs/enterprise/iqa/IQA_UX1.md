# IQA Analysis UX-1 — operator-facing first result (PUBLIC-SAFE)

Tracking: [#145](https://github.com/delphykmc/pixelscope/issues/145). PR base:
`handoff/enterprise-iqa-window@6c51c703b4b9054f99bc57910de89845a09df7df`
(#144 merged). Upstream generic Host MAIN pin:
`95b7845e731302934e21033a0ee09ef08947495a`.

This is a design/implementation **review candidate**, not a finalized
Enterprise product. Only downstream public-safe code/tests/docs change; do not
merge any of it into PUBLIC MAIN or mistake the synthetic fixture for server
truth. Original owner decision (#137) to use an independent nonmodal single
pair window with linked A/B/Map and right Inspector remains intact.

## Owner UX-1 feedback round 2 (accepted 2026-10-09)

1. **Single per-Attribute Display Range ±R:** approved OFFICIAL signed
   difference bars and the selected Spatial Map use exactly the same
   numeric visualization span. Changing R alters bar and Map display only;
   measurement data is never modified. A +7 dB value at ±4 dB clips,
   but at ±10 dB is 70% of the positive half-axis without clipping.
2. `chart_axis_range` declares comparability and an initial range
   preference, **not a second user-controlled axis**. If it is missing,
   no official bar is fabricated; a Map can still use `fixed_range`.
   This protects against unverified scientific or unit equivalence.
3. **A | Map | B** is the default visual order. `Alt+X` and the header
   button toggle **B | Map | A**, keeping the Map centered and preserving
   source A/B identity, data, polarity, ROI and zoom.
4. **One header legend** names B-better (negative, blue) and A-better
   (positive, red); neutral signed values use teal/purple and never infer
   a winner. Rows are **36px** with no per-row ±ticks/endpoint labels.
   Official/ROI/Map summaries are independent labeled cards in a
   scrollable lower Inspector section.
5. **Pixel ROI:** source coordinates round outward to covered integer
   pixels, including when validating an earlier fractional saved ROI.
   The user sees integer (x,y,w,h) and pixel area rather than subpixels.
6. **Styling:** the downstream window uses MAIN's public `TOKENS` and
   the standalone demo calls `apply_engineering_palette`. No competing
   private theme or public MAIN source modification.
7. **Visual fixture:** `--rgb` now creates patterned 4K A/B PNG images
   with gradient, grid, edges, circles and asymmetric position landmarks.
   This makes zoom/pan/alignment visible unlike flat DC images.

## Owner-approved group mapping (2026-10-09, round 3)

Owner approved the proposed group-based Inspector and **fixed-unit range
mapping (Option A)**, NOT data-dependent min/max normalization:

- Group dynamically by exact validated `unit`, in first-appearance order.
  Prototype has `dB` (10 metrics) and `delta` (2 metrics); future
  additional units create their own sections. Existing `AttributeDisplay.group`
  is only a secondary metric-family label, **not** the unit-range key.
- Each unit section exposes exactly **one symmetric ±Range**, adjusted in
  0.5 increments. All official bars in that unit section use the same
  range; the selected Map uses that range if it belongs to the section.
  Initial range comes from the maximum **adapter-declared** official
  chart-axis default or Map fixed display range within that unit,
  rounded upwards to a 0.5 increment; never inferred from pixel content.
- One `Map Display Gain ×` at Inspector top, default ×1.0, selectable
  ×0.5 steps (0.5–10.0 in this prototype). It affects only visualization
  of the selected spatial grid across any unit, not official bars, RGB or
  GRID-DERIVED ROI statistics.
- `official_bar_fraction = clip(official_value / unit_range, −1, +1)`
  **only when the official adapter has declared numerical compatibility**
  via `chart_axis_range`. Otherwise display text **unscaled**.
- `map_color_fraction = clip(grid_value × map_gain / unit_range, −1, +1)`.
  Invalid cells stay transparent, signed zero stays centered and clamped
  counts are computed *after gain*. Underlying spatial values and
  verified OFFICIAL measurement are immutable.
- Per-result `analysis_state.ranges` is now keyed by `unit` and an
  explicit `display_gain` is saved. Legacy H1 state with attribute-ID
  ranges and no gain is accepted and deterministically migrated:
  first source-order override within each unit, except the currently
  selected Attribute's override wins its unit. Values are rounded
  **upwards** to valid 0.5 increments. New saved states validate
  unit membership and half-step ranges/gain (no arbitrary dict keys).
  Original ROI / viewport state continues unchanged.
- When changing units or their range, do not rebuild A/B/Map Qt scenes,
  clear ROI or reset linked navigation. Unit bars update in place;
  changing Map gain redraws only its single grid pixmap.

## Final operator readability and FHD resizing polish (2026-10-09)

The owner approved grouped Range/Gain behavior and native tests, and requested
a final explanatory-layout pass before merging UX-1.

- The **relative Attribute chart** and **analysis details** are now vertically
  stacked in one **draggable QSplitter**, with non-collapsible panes, a visible
  8px handle and independent scroll areas. At FHD, they expand to occupy
  the available Inspector height rather than leaving a fixed empty strip.
  Drag the divider to devote more height to either chart or details.
- The details pane clearly identifies the **selected Attribute name/unit**,
  and groups the three analysis domains into labeled, expanding cards.
- **OFFICIAL · FULL PAIR:** producer-verified full-image-pair A/B difference;
  never a locally calculated ROI or average of a Map.
- **ROI ANALYSIS · SOURCE PIXELS:** an integer source-coordinate rectangle.
  A valid-cell area-weighted **GRID-DERIVED** mean is a spatial estimate;
  it is not an official per-ROI model score. Coverage means the fraction
  of ROI pixels supported by valid spatial cells.
- **SPATIAL MAP · CELL STATISTICS:** signed grid values are displayed as
  nearest-neighbor cells. The color endpoints use the selected unit
  Range ±R and shared Map Gain ×G; invalid cells are transparent, and
  clipped cells are valid cells saturated at the endpoint color. The
  producer's underlying Grid and official metrics remain unchanged.
- The lower cards share spare vertical height; the chart and details
  remain separately scrollable. Existing result, ROI, keyboard navigation,
  T swap, map-only repaint and saved user state contracts are unchanged.

For owner visual acceptance, resize the Analysis Window to 1920×1080 and
drag the **horizontal divider inside the right Inspector** in both directions.
Verify the chart remains keyboard-selectable, cards remain legible at high
and low detail allocations, and changing Attribute updates the details
heading. See `test_ux1_fhd_inspector_splitter_and_metric_explanations`
for focused Qt geometry and semantics regression.

## Operator sequence

1. A first result shows identity, source labels/dimensions and a compact **Fit
   pair / Shift+drag ROI** row, with three spatially aligned views.
2. The main Inspector **relative difference** display presents supplied
   Attribute order in two columns: label+group+unit and an interactive
   **official** bipolar bar. Clicking/arrow-key selecting a row picks a Map.
   First opening prefers the first supplied Attribute with **both official
   value and a spatial grid**, without ranking different attributes/units;
   if none exists, it selects the first supplied Attribute. Explicit user
   selection and restored per-result state always take priority.
3. Bar direction means **A better (+)/B better (−)** only when the adapter
   declared `quality_oriented=True`. Neutral signed values use the
   independent purple/teal polarity and never infer a winner.
4. The chart uses validated per-unit **Range ±R**, not per-attribute
   controls. Map colors further multiply Grid values by one shared
   **Display Gain**. Missing `chart_axis_range` prints unscaled (no
   fabricated official bar). Missing Official prints
   **MISSING/PARTIAL/FAILED**, not zero. True zero is centered; clipped
   values retain their original signed measurement.
5. Group labels are repeated per Attribute without sorting or coalescing:
   discontiguous same-group records keep the verified server/supplied order.
   No cross-group magnitude ranking or globally comparable maximum is
   implied. Current synthetic axis ranges are **illustrative**, not a model
   or server contract.
6. Selecting a different Attribute or editing the shared Display Range **does not
   rebuild** any A/B or Map `QGraphicsScene` or persistent ROI overlay. Only
   the selected Map item's grid-resolution pixmap, grid transform, placeholder,
   Inspector and pane caption update. Deliberate Result replacement
   reconstructs scenes and retains per-result state.
7. The Map displays **declared grid cells at nearest/fast transform**, not
   interpolated per-pixel precision. The legend names cell original-pixel
   footprint and transparent invalid-mask count, distinct from *true zero*
   and clamped valid counts.
8. Save/Open portable, hotspots, official local scores, report Export and live
   server/jobs are **not** implied by this UX; they remain #140/#141 H2-H5.

## Review fixture coverage

The 12-metric 3840×2160 public synthetic result has a 64px spatial grid and
deliberately tests independent official/map availability:

| Synthetic row | Official scalar | Map | Purpose |
|---|---|---|---|
| 1 | Present | Missing | Official-only chart, no Map |
| 2 | Missing | Present | Valid Map, not false official zero |
| 3 | True zero | Present | Visible zero tick, no positive/negative bar |
| 4 | Small nonzero | Present | Distinct from zero |
| 5/6 | Large positive/negative | Present | Explicit chart clipping |
| 7–10 | Present | Present | Mixed ordinary oriented values |
| 11 | Present, neutral signed | Present | No winner/purple-teal |
| 12 | Missing | Missing | Honest empty chart/map |

The default standalone demo has neither original RGB image; both show source
unavailable with the grid still functional. Running the demo with `--rgb`
creates two safe patterned 3840×2160 PNGs (grid/gradient/edges/circles/landmarks)
and displays them in A/B, deleting them after the window exits. A separate Qt regression writes a
safe 3840×2160 RGB fixture and confirms source panes, repeated 12-attribute
selection, persistent scene identities and a real QImage screenshot.

## Windows owner validation (separate Python processes)

```powershell
$py = Join-Path $env:USERPROFILE "mycode\pixelscope\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { throw "Locate a valid Python 3.10 environment" }
$env:PYTHONPATH = (Resolve-Path .\src).Path
& $py -m pytest -q tests/enterprise/iqa/test_analysis_model.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_analysis_window.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_analysis_ux1.py
& $py -m pytest -q tests/iqa_reference/test_reference_extension.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -m pixelscope_enterprise.iqa.demo
# Optional: local synthetic 4K A/B geometry patterns, removed at exit.
& $py -m pixelscope_enterprise.iqa.demo --rgb
```

Check a 1920×1080 physical desktop with 12 metrics and scroll the Inspector;
take FHD capture at top and scrolled positions. Verify first insight,
selected Map context, per-unit dB range ±4 vs ±10 for a +7 dB
official scalar and independent delta range, source-missing fallback,
shared Map gain ×1 vs ×2, one legend and 36px row density,
integer ROI and structured Official/ROI/Map cards. Test the A/Map/B
and B/Map/A toggle with Alt+X, then the non-DC 4K patterned RGB case. Check Shift cursor/Clear ROI, wheel,
keyboard chart navigation, per-result restoration and multiple normal-GC
close/reopen cycles. Do not claim Qt success solely from generic public CI:
Enterprise-native PySide6 tests remain owner-local under CI policy.

## Review and next phases

UX-1 is ready for an independent code review and visual sign-off **after**
CI/static and the owner Windows test/screenshot feedback. Do not merge the
next PR to handoff without this gate. H2 file reopening of a fresh, equivalent
`AnalysisResult` instance currently fails the intentional immutable-ID
guard; define provenance/dedup semantics only with the reviewed #140 reader.
UX-2 adds linked cursor/hotspots and stronger spatial analysis with explicitly
defined valid coverage. #139 status/closeout is independent MAIN tracking.
