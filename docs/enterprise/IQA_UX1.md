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
4. The chart uses `AttributeDisplay.chart_axis_range`, a strictly positive,
   separately provided display half-axis. Map `fixed_range` is **not** a
   chart axis. Unknown official axis prints numeric scalar and **Axis not
   supplied**, with *no bar*. A missing official scalar prints
   **MISSING/PARTIAL/FAILED**, not zero. Genuine official zero is a
   zero-width bar against a visible zero tick. A clipped bar announces
   `clipped`, but the original scalar remains unchanged.
5. Group labels are repeated per Attribute without sorting or coalescing:
   discontiguous same-group records keep the verified server/supplied order.
   No cross-group magnitude ranking or globally comparable maximum is
   implied. Current synthetic axis ranges are **illustrative**, not a model
   or server contract.
6. Selecting a different Attribute or editing Map color scale **does not
   rebuild** any A/B or Map `QGraphicsScene` or persistent ROI overlay. Only
   the selected Map item's grid-resolution pixmap, grid transform, placeholder,
   Inspector and pane caption update. Deliberate Result replacement
   reconstructs scenes and retains per-result state.
7. The Map displays **declared grid cells at nearest/fast transform**, not
   interpolated per-pixel precision. The legend names cell original-pixel
   footprint and transparent invalid-mask count, distinct from *true zero*
   and clamped valid counts.
8. Save/Open portable, hotpots, official local scores, report Export and live
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
unavailable with the grid still functional. A separate Qt regression writes a
safe 3840×2160 RGB fixture and confirms source panes, repeated 12-attribute
selection, persistent scene identities and a real QImage screenshot.

## Windows owner validation (separate Python processes)

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q tests/enterprise/test_analysis_model.py
.\.venv\Scripts\python.exe -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_window.py
.\.venv\Scripts\python.exe -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_ux1.py
.\.venv\Scripts\python.exe -m pytest -q tests/iqa_reference/test_reference_extension.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pixelscope_enterprise.iqa.demo
```

Check a 1920×1080 physical desktop with 12 metrics and scroll the Inspector;
take FHD capture at top and scrolled positions. Verify first insight,
selected Map context, official-vs-spatial axes, source-missing fallback,
legend text/invalid grid cells, ROI and relative chart alignment. Repeat
with a safe 4K RGB source-present case. Check Shift cursor/Clear ROI, wheel,
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
