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

Cards report GRID mean signed values and coverage, not OFFICIAL per-ROI
scores. Their ranking headings say **LARGEST LOCAL DIFFERENCE**, **NEXT
STRONGEST**, **THIRD STRONGEST**, with a small bar normalized only against the
current #1 candidate (`score / rank1.score`). This is not an absolute
severity measure or quality winner and is tooltip-labeled accordingly.
The first card receives higher-contrast emphasis; Attribute overview
similarly labels its first OFFICIAL card **LARGEST GLOBAL DIFFERENCE**.
A one-line visible description clarifies sorting and ROI provenance, rather
than hiding the critical distinction only in a tooltip. Missing/zero official scalars retain exploratory-mode labels.
Clicking a card uses the selected source ROI, updates the existing ROI
Inspector and centers A, Spatial Map and B at one common source-pixel
zoom. Existing scenes are never rebuilt on candidate or Attribute selection.
This intentionally changes zoom because focus is a user action; ordinary
Attribute changes and Map Gain adjustments preserve viewport.

Optional `Show hotspot boxes` (View / top toolbar, Alt+H) overlays
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
  free to expand/float later. No continuous resize override; native UX-1
  splitter must still grow when window size increases.
- Source-native A/B crops are now drawn in **one widget**, not padded
  independent QLabel viewers. Pixel identity, map science and ROI focus
  remain unchanged. Regression tests assert FHD inspector height,
  stitched canvas scaling and stable QPixmap cache keys across resize.

Visual references: [NVIDIA ICAT](https://www.nvidia.com/en-us/geforce/technologies/icat/)
for co-aligned A/B image inspection; [NN/g visual hierarchy](https://www.nngroup.com/articles/principles-visual-design/)
for emphasizing the first ranked finding through labels, contrast and
relative strength rather than relying on bare ranking numerals.
