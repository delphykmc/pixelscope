# IQA UX-2 — guided difference inspection (PUBLIC-SAFE)

Parent [#145](https://github.com/delphykmc/pixelscope/issues/145). Last accepted UX-1:
[PR #146](https://github.com/delphykmc/pixelscope/pull/146), handoff SHA
`69888cabcdf21946d15649653f35037027524bcf`. **Never target PUBLIC main.**

## Operator product direction

A single pair, three linked source-coordinate panes (A | Map | B) and a right
resizable Inspector. Move from a diagnostic number table to **recognize the
meaningful difference -> find its spatial cause -> verify with native A/B crops**.
Full-image official numbers, grid-derived estimates and visual presentation
controls must always be explicitly distinguished.

### UX-2A — first insight and action surface (#147; current PR)

- Three rounded, clickable cards occupy a compact strip above the 3-pane viewer.
  Rank only `AttributeDisplay.unit == "dB"` on the absolute **OFFICIAL**
  signed full-pair difference. A negative signed value stays negative in text.
  Never mix `delta` with `dB` or imply a quality winner for a neutral metric.
- **Eligibility must be verified:** `official_availability == "available"`,
  `chart_axis_range` declares comparable official display semantics,
  `abs(official_value) > 0.3 dB`, and `summary_signal_gate is True`.
  The new optional nullable PUBLIC-SAFE **presentation metadata** field means:
  trusted upstream adapter has verified **at least one A/B signal component
  strictly above -50 dB relative to the original signal**. Its exact private
  algorithm/wire fields are not part of this PR. `None` means UNKNOWN and
  must not rank; `False` means gate failed. No attempt to deduce power from
  relative signed delta or the spatial grid. Ties keep supplier Attribute order.
- **Owner color pass:** the Top-3 row uses subtly tinted raised-panel cards,
  with an A (muted red), B (muted blue), or ± (muted violet) badge; signed-neutral
  metrics have **no winner** label. Hover and selected cards have separate
  contrast and borders; the icon/text jointly encode meaning so color alone
  is never required. Disabled/unknown cards remain neutral. No user-level
  change to measured values, source polarity or chart grouping.
- Clicking a card selects that Attribute exactly as chart selection does.
  Existing ROI, source pixel coordinates, zoom, unit range and Map Gain survive;
  A/B names and polarity remain immutable. Cards still show verified official
  values when their selected Attribute has no spatial grid; the Map pane
  correctly says unavailable.
- The generic Qt window now has a real nonmovable `QToolBar` shared with
  View-menu `QAction` objects: Fit (Ctrl+0), source **positions** swap
  (T, Alt+X), Clear ROI (Esc / Shift+Esc). Recognizable vector-painted
  monochrome glyphs work offline and without third-party icons. Unlike the
  old pushbuttons in the header, action text, state, shortcuts and tooltips
  have one source of truth. The standalone 4K fixture explicitly marks
  simulated signal-eligibility cases, not an actual server measurement.
- Top-3 eligibility is a **first-screen interpretation only**: never modify
  `AnalysisResult` measurements, `roi_statistics`, group range or Map gain.
  Missing eligibility produces an explicit verification-pending state, rather
  than an invented Top 3.

### UX-2B — spatial proposal engine (#148; next PR)

Algorithm acceptance discussion: only use raw signed valid `SpatialMap`, not
clamped UI colors; source-pixel 512×512 default, 128-pixel scan step including
edge windows, true clipped cell areas and valid mask, default coverage >=80%.
Use sign-aligned local GRID-DERIVED mean as a *candidate score*, not OFFICIAL
local score. Keep 3 candidates with deterministic non-overlap filtering
(proposed IoU <= 0.1). For zero/missing official scalar, use a labeled
exploratory absolute-mode **only if approved**, otherwise no sign-aligned
ranking. On-demand candidate computation/caching, no eager 12-attribute scan
at initial window presentation. Linked pixel cursor, 512px ROI action/preset
and keyboard restoration are also part of this slice.

### UX-2C — crop evidence and optional boxes (#149; following PR)

On selecting an attribute, show top 3 candidate crops as original-resolution,
pixel-aligned `A | B` stitch comparisons, with an explicit seam and coordinates.
Selecting a candidate focuses linked views and updates the source-pixel ROI.
Numbered overlays optional; unmodified native images recoverable via one
Show/Hide toggle. Do not paint nonexistent RGB sources or imply Map-derived
estimates are official. Load/crop large source images outside blocking GUI
work where needed; show actual busy/progress feedback, avoid false 0–100%.
Result switch discards stale work and restores per-result inspection state
without modifying signed science.

## QA gates

| Gate | UX-2A | UX-2B/C |
| --- | --- | --- |
| Pure Python model tests | Ranking + gates/ties/missing | signed/negative/ties/masks/partial edges |
| Qt (Windows PySide6 6.4.2) | Action/shortcut, 3 cards, scene/ROI persistence | cursor/512 ROI, crop selection/overlay/teardown |
| Manual FHD | readable cards + Inspector splitter + native toolbar | three crops, linked viewport + optional boxes |
| Synthetic 4K | source present/absent, mixed unit/availability | 64px grid, ROI/search latency + invalid regions |
| Static CI | change-scoped Ruff/format/mypy | change-scoped Ruff/format/mypy |
| Boundaries | Enterprise-owned paths only; handoff PR | no server, auth, private codec or PUBLIC main |

Run as separate Windows processes (the existing normal-GC practice):

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q tests/enterprise/test_analysis_insights.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_ux2a.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_ux1.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_window.py
& $py -m pytest -q tests/enterprise/test_analysis_model.py
& $py -m pytest -q tests/iqa_reference/test_reference_extension.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -m pixelscope_enterprise.iqa.demo --rgb
```

Do not treat generic E4 screenshots as proof of Enterprise Qt GUI behavior,
and do not merge this PR until exact-HEAD static CI and native Windows acceptance.
