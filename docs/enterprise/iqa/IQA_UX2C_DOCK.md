# UX-2C — independent bottom Spatial Candidate Dock (PUBLIC-SAFE)

Tracking [#149](https://github.com/delphykmc/pixelscope/issues/149);
depends on merged UX-2A #150 and UX-2B #151 at
`handoff/enterprise-iqa-window`. **Never target PUBLIC MAIN.**

## Workflow and containment

The Enterprise `AnalysisWindow` is its own QMainWindow. It owns an
`enterpriseIqaSpatialCandidatesDock` QDockWidget with a unique object name,
placed initially in BottomDockWidgetArea. Users can hide, redock or float
it; the View menu exposes its native toggle action. Dock state is persisted
in `QSettings("PixelScope", "EnterpriseIqa")` under the *dedicated*
`analysis_window_spatial_dock_state` key. It cannot modify MAIN dock
registration, contents, stored window state or user shortcuts.

Dock title controls directly reuse `pixelscope.ui.plots_dock_title.PlotsDockTitleBar`
through a minimal IQA subclass with an isolated geometry-key registry,
plus the MAIN `_WorkspaceDockTopLevelController` floating-normalization
behavior: reattach retained Qt title widgets and detach transient parent
safely after QDockWidget's native float transition.
They provide identical platform-independent Qt-drawn **Float/Dock,
Maximize/Restore, Hide** icons, work-area-safe floating maximize, saved
normal geometry and bounded shutdown. Floating geometry uses
`ui/enterprise_iqa_spatial_floating_geometry`; it is separate from the
MAIN Plots key. There is no separate Minimize action in the MAIN Plot title
bar: Hide is the same close-button behavior as MAIN.

The selected Attribute drives at most three candidate cards. Each card
displays the same immutable source-pixel ROI coordinate from original A and B,
within one A|B stitched canvas with a narrow central seam and no
individual A/B black-padded viewers. `QPixmap.copy(QRect(x,y,w,h))` extracts
the exact source-native ROI **once on selection**, then the canvas's
`QPainter.paintEvent` fits both cached crops with one shared scale into the
actual available width/height. Resize only repaints cached QPixmaps; no crop
decode, `QPixmap.scaled` or child-label clearing on every dock height change.
The pair fits while preserving source ROI aspect ratio and contains no inner
gutters. Very tall docks may have **outer** letterboxing after full width fit
to avoid distorting/truncating the ROI. This is display-only, never analyzed. When source RGB is missing, each half
explicitly reads source unavailable while GRID-DERIVED ROI score, position
and valid coverage remain selectable. No private server/reader/auth content
or model images are embedded in this repository.

Cards report GRID signed local mean and validity coverage, never OFFICIAL
ROI scores. Ranking is conveyed by **small circular 1/2/3 badges** and a
relative strength bar normalized to the leading search candidate
(`score / rank1.score`). **#1 uses the same muted red (#e5857d),
hover/checked color blending (14/22/30%), strong border, and a small vector
star** as the Attribute Top-3 visual system. Other ranks have subdued
blue-grey tones; selected cards have visibly filled tinted backgrounds
rather than merely changed outlines. This is a relative local search
ranking, not an absolute severity or quality-winner indicator.
The global OFFICIAL cards use compact **★ 1 / 2 / 3** tokens. The small
**GRID** chip and tooltips keep provenance visible without verbose
on-screen rank sentences. Missing/zero official scalars retain exploratory-mode labels.
Clicking a card uses the selected source ROI, updates the existing ROI
Inspector and centers A, Spatial Map and B at one common source-pixel
zoom. Existing scenes are never rebuilt on candidate or Attribute selection.
This intentionally changes zoom because focus is a user action; ordinary
Attribute changes and Map Gain adjustments preserve viewport.

Optional `Show Hotspot` with an in-house Qt-painted crosshair icon
(View / top toolbar, Alt+H) overlays
numbered cosmetic rectangles in the three original-coordinate scenes.
Boxes are not painted on missing RGB sources, and the Map can be absent.
Disabling the toggle returns original RGB displays unchanged; source A/B
meaning and swap orientation are never mutated.

## Scan scheduling and bounds

- Scan policies exposed to the operator: Detailed 64px, Standard 128px
  (default), Fast 256px. `find_spatial_candidates` itself applies the
  preallocated resource ceiling introduced in #151.
- The selected Attribute alone is scanned on demand in a
  single-worker `ThreadPoolExecutor`, not all 10–12 metrics on startup.
  A small Qt timer polls completion on the GUI thread. Only GUI thread
  touches pixmaps, labels, QGraphicsScenes or selected ROI.
- Candidate cache key: **immutable result_id, attribute_id, stride**. No
  image-dependent display gain or normalized range participates.
- Switching result/Attribute/stride invalidates presentation of stale
  completion; pending queued futures are canceled where possible.
  Closing the window stops polling and reopening may reuse cached results;
  Manager.shutdown disposes the worker. No invented 0–100% progress,
  just an explicit work-in-progress message.
- Invalid geometry or scan-budget `ValueError` yields a safe unavailable
  notice. No arbitrary stride input, no false official result.

## Gate and integration

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_ux2c.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/test_analysis_ux2a.py tests/enterprise/test_analysis_ux1.py
& $py -m pytest -q tests/enterprise/test_spatial_candidates.py
Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
& $py -m pixelscope_enterprise.iqa.demo --rgb
```

Windows manual: FHD/4K DPI 100/150/200%, resize main three panes, dock
hide/float/restore, A/B swap, card focus, boxes on/off, missing RGB,
quick Attribute/result switches, clean normal-GC close/shutdown. Source
preview should be visually pixel aligned at the same crop. Generic E4
screenshot CI cannot confirm Enterprise dock behavior.

## Windows owner-reported UX regression and repair

- PySide6 6.4 returns a **null `QPixmap` instance** from an empty QLabel,
  not necessarily `None`. The original missing-source Qt test incorrectly
  asserted `pixmap() is None`; the new stitched canvas exposes explicit
  `has_a`/`has_b` rather than relying on QLabel's binding return type.
- The default dock squeezed the UX-1 Inspector at 1600×800. A one-time
  initial FHD dock compacting step requests ~175px while leaving the user
  free to expand/float later. No continuous resize override. Historical UX-1
  Inspector test hides the optional Dock **after first show**; a separate
  UX-2C test exercises FHD layout with Dock visible.
- Qt QSettings dock `restoreState()` may resurrect a previously hidden dock
  or restore a floating panel off a disconnected display. **First show only**
  explicitly restores discoverability (and re-docks offscreen floats); View
  toggle/hide still works thereafter. Add saved-hidden-layout regression.
- Prior broad `SpatialCandidatesPanel.setStyleSheet()` generated PySide6
  `Could not parse stylesheet` warnings. Replaced with minimal, scoped
  per-control QSS: cards, rank tokens, bars, labels. Scientific strings
  shortened to Δ, coverage and a GRID provenance chip, with details in tooltips.
- Tests must follow displayed UI semantics (old `GRID mean` literal is now
  `Δ` accompanied by a GRID provenance badge).
- Source-native A/B crops are now drawn in **one widget**, not padded
  independent QLabel viewers. Pixel identity, map science and ROI focus
  remain unchanged. Regression tests assert FHD inspector height,
  stitched canvas scaling and stable QPixmap cache keys across resize.

Visual references: [NVIDIA ICAT](https://www.nvidia.com/en-us/geforce/technologies/icat/)
for co-aligned A/B image inspection; [NN/g visual hierarchy](https://www.nngroup.com/articles/principles-visual-design/)
for emphasizing the first ranked finding through labels, contrast and
relative strength rather than relying on bare ranking numerals.

## October 10 final owner-requested refinements

- Unified ROI #1 emphasis with Attribute cards: muted **red** instead of
  yellow, distinct filled **checked** state, star-marked #1.
- Renamed `Show hotspot boxes` to **Show Hotspot** and added a compact
  crosshair/ROI vector toolbar icon, without changing Alt+H semantics.
- Replaced broken OS-native QDockWidget float/close chrome with the
  production Plots title controller. Test float/dock, maximize/restore,
  hide, tooltip and icon parity on Windows and secondary monitors.
- Corrected the stale UX-2A `NOT YET VERIFIED` assertion to the concise
  `SIGNAL PENDING` label; eligible Top-3 list remains empty and disabled.


## Handoff full-suite contract boundary

The temporary Enterprise handoff branch intentionally carries
`src/pixelscope_enterprise/`, `tests/enterprise/`, and `docs/enterprise/`
alongside the PUBLIC MAIN sources. Thus PUBLIC MAIN's architectural guard
`tests/unit/test_issue121_iqa_reference_architecture.py::test_enterprise_reserved_paths_are_not_owned_by_main`
**must fail on this combined handoff tree**; it verifies an invariant for the
standalone PUBLIC MAIN publication tree, not this temporary integration
snapshot. **Do not relax/delete/skip it in MAIN.**

For a handoff-local near-full-suite run retaining every other test:

```powershell
& $py -m pytest -q --deselect=tests/unit/test_issue121_iqa_reference_architecture.py::test_enterprise_reserved_paths_are_not_owned_by_main
```

The other reported full-suite failure
`test_repeated_mouse_roi_replaces_actual_viewport_pixels_without_resize`
was a stale assertion that counted *all* `QGraphicsRectItem` instances:
UX-2C intentionally added three always-present (normally hidden) hotspot
rectangles next to the **single** ROI edit rectangle. The updated regression
still requires exactly one live ROI identity, no new scene objects after
repeated ROI drags, and no stale yellow viewport pixels.
