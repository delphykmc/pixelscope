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
with A|B adjacent previews separated by a narrow visible seam. Preview
`QPixmap.copy(QRect(x,y,w,h))` extracts the exact ROI; scaled thumbnails are
**display-only**, never analyzed. When source RGB is missing, each half
explicitly reads source unavailable while GRID-DERIVED ROI score, position
and valid coverage remain selectable. No private server/reader/auth content
or model images are embedded in this repository.

Cards report GRID mean signed values and coverage, not OFFICIAL per-ROI
scores. Missing/zero official scalars retain exploratory-mode labels.
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
