# Network input and viewer interaction performance

Status: Active
Owner: ChatGPT under owner authorization
Branch: `perf/network-interaction-followup`
Last updated: 2026-10-16

First slice: owner accepted, PR [#188](https://github.com/delphykmc/pixelscope/pull/188).
Remaining acceptance and behavior work below keeps the broader plan active.

## Goal and scope

Measure the reported two-file drop, Files selection/deselection, Display Gain and
Folder Position Difference workflow after PR #187. Reduce proven GUI work while
preserving source pixels, async cancellation, registration intent and native
geometry. No packaging, dependency, IQA or CI expansion. The diagnostic-only
`diagnostics/perf-3way-regression-20261016` branch is not merged into production.

## Evidence and design

Synthetic Windows CPython 3.10/offscreen 3840x2160 RGB8 resident-pair probe,
six repetitions, requested 1500x950 window, isolated INI settings. Dispatch plus
one `processEvents()` call is observational GUI processing, not monitor scanout.
V1 selection observations were 184.58–258.30ms; V3 141.96–167.58ms.
The V1 cProfile attributed 811ms of 1,473ms accumulated selected work to
pyqtgraph levels/rescale conversion, even though previews are already uint8.
V3 still supplies the same redundant `(0,255)` levels. Use the uint8 QImage
passthrough and verify actual pixel colors, alpha and mapped geometry.

The image-surface drop filter calls `Path.is_dir()` and `is_file()` on the GUI
thread before enqueueing. Let the existing registration discovery worker classify
all paths; retain registration-only folders and ordinary mixed-drop semantics.

For uint8 display conversion, evaluate the unchanged float32 affine/gamma
calculation on 256 codes and index the result. This preserves rounding/clipping
and avoids a 94.92MiB float32 working allocation for each UHD RGB8 task.

Display Gain currently publishes separately per viewer. The preliminary gain
probe timed out for some worker completions; its results are not used. A subsequent
probe using an actual Qt event loop completed both sources reliably (below).
Folder Position removes Difference
also on V1, as required by the current passive-selection lifecycle. A dedicated
navigation intent requires a separate behavior change and regression coverage.

## Validation plan

Add deterministic GUI filesystem-prohibition drop tests and rendered QImage
pixel tests. Run related registration, Quick Compare, Display Gain, geometry and
lifecycle coverage, Ruff, mypy, docs and diff checks. Re-run the same selection
probe after changes. Real SMB, Explorer interaction and monitor-visible
synchronization require owner/manual acceptance; synthetic timing is not that gate.

## Progress

- 2026-10-16: Read current state, ownership documents, source and related tests;
  fetched the diagnostic branch and PR #187 main. Created independent historical
  detached worktrees under ignored `temp/`. Existing owner untracked files untouched.
  No commits or GitHub writes yet.

## Observed candidate results

Sequential re-run, six repetitions including first iteration, same environment
and cProfile overhead, no concurrent validation process:

| Revision | pair selection median ms | deselection median ms |
| --- | ---: | ---: |
| V1 `36f672b` | 258.70 | 42.56 |
| V2 `00b7dd7` | 271.05 | 55.23 |
| V3 `21c3158` | 146.20 | 16.74 |
| candidate | 24.95 | 15.45 |

V3 accumulated 700ms in `rescaleData` out of 1,014ms profiled selection work;
the candidate no longer enters that path. V1 teardown also emitted historical
deleted-TaskSignals errors; that old revision is not claimed lifecycle-clean.
These resident synthetic measurements do not establish cold/network decoding,
drop-to-paint, drag-hover or monitor-visible latency. V2's selection median is
slower than V1 in this run; PR #187 is substantially faster on this specific path.

Isolated core 4x gain conversion, UHD RGB8, one warm-up and ten repeats:
V3 median/max **89.76/91.95ms**, candidate **65.10/68.97ms**. This measures only
conversion, not worker queue time, synchronization or final paint. No uint16,
RAW/Bayer or physical SMB speedup is inferred.

Post-validation two-source UI gain probe: production composition, two resident
UHD RGB8 sources, Multi View, isolated INI settings, eight successive gain changes
`2,4,8,16,2,4,8,16`. A local `QEventLoop.exec()` runs until both occupied viewers
have accepted the requested gain and both workers finish, then `processEvents()`
handles pending painting. V3 median **243.53ms** (240.23–284.75ms), candidate
**71.16ms** (69.41–103.13ms). This is Qt event processing, not monitor scanout or
an atomic-publication guarantee, and does not include a Difference tile. The
earlier short-`QTest.qWait` probe's timeout was not reproduced with this event-loop
probe; its root cause is not established. No production worker behavior was changed
to accommodate it.

Temporary probes and raw local logs remain ignored under `temp/`, as required by
the quality contract, and are not production artifacts. Commands observed:

```powershell
.venv/Scripts/python.exe temp/perf_selection.py temp/perf-v3 V3
.venv/Scripts/python.exe temp/perf_selection.py . AFTER
.venv/Scripts/python.exe temp/perf_selection.py temp/perf-v2 V2
.venv/Scripts/python.exe temp/perf_selection.py temp/perf-v1 V1
.venv/Scripts/python.exe temp/perf_gain_math.py temp/perf-v3 V3
.venv/Scripts/python.exe temp/perf_gain_math.py . AFTER
.venv/Scripts/python.exe temp/perf_gain_eventloop.py temp/perf-v3 V3
.venv/Scripts/python.exe temp/perf_gain_eventloop.py . AFTER
```

## Validation record

- Initial image rendering/Quick Compare selection: **21 passed in 12.60s**.
- Gain math/viewer/shortcut selection: **34 passed in 5.27s**.
- Combined registration/Open/Files drag/Quick Compare/preview/spatial/gain/RAW
  selection: **113 passed in 32.59s**. Includes worker-blocked direct/folder/mixed
  drops with GUI event progress, exact rendered Gray/RGB/RGBA pixels and alpha
  without rescaling, all 256 uint8 values against float32 mapping with twelve
  gain/gamma combinations and strided RGB input.
- An earlier command named nonexistent `test_p3b_raw_display_gain_core.py` and
  collected no tests; corrected to the existing `test_p3b_raw_display.py` above.
- Ruff check passed; format check: **348 files already formatted**. Only the
  three pre-existing owner GC scripts were excluded. Mypy: **108 source files,
  no issues**. `pip check`: **No broken requirements found**. Documentation
  contract and `git diff --check` passed before final evidence updates.
- Restricted full-suite attempt was stopped after failures; the diagnostic
  `.venv/Scripts/python.exe -m pytest -x -q` isolated **1 failed, 46 passed in
  21.06s**: sandbox denied creation of an integration-test temporary `.git/config`.
  No product assertion or test was relaxed.
- Normal Windows permissions, implementation commit `c7596a6`:
  `.venv/Scripts/python.exe -m pytest -q` — **1513 passed in 366.67s (0:06:06)**,
  normal automatic GC, no skips, masks or timeout increases.

The combined focused command was:

```powershell
.venv/Scripts/python.exe -m pytest -q tests/ui/test_open_images_registration.py tests/ui/test_large_folder_registration.py tests/ui/test_large_folder_registration_composition.py tests/ui/test_large_folder_registration_lifecycle_review.py tests/ui/test_files_drag_selection_debounce.py tests/ui/test_preview_passthrough.py tests/ui/test_issue75_viewer_coordinates.py tests/ui/test_issue77_wp_c_quick_compare.py tests/unit/test_display_gain_core.py tests/unit/test_p3c_display_gain_core.py tests/unit/test_p3b_raw_display.py tests/ui/test_p3c_display_gain.py tests/ui/test_p3b_raw_display_gain.py tests/ui/test_p3b_display_gain_shortcuts.py tests/ui/test_multiview_gain_diff_stability.py
```

## Delivered first slice and provenance

- 2026-10-16: Owner confirmed the improvement and explicitly authorized merging
  PR #188. All executed PR checks passed at `40749db` (focused Windows job was
  scope-skipped); the accepted source/tests remain identical to the full-tested
  implementation commit `c7596a6`. The owner confirmation is not a claim that the
  entire detailed SMB/Explorer scenario matrix was performed.

- `src/pixelscope/ui/image_viewer.py`: final-preview QImage passthrough.
- `src/pixelscope/core/display_transform.py`: exact uint8 transform lookup.
- `src/pixelscope/ui/quick_compare.py` and
  `src/pixelscope/app/registration_controller.py`: worker-side drop classification,
  retaining direct-file completion and ordinary mixed/folder behavior.
- `tests/ui/test_preview_passthrough.py`,
  `tests/ui/test_issue77_wp_c_quick_compare.py`,
  `tests/unit/test_display_gain_core.py`: changed-contract coverage.
- `docs/ARCHITECTURE.md`, `docs/CURRENT_STATE.md` and this plan: narrow cumulative
  contract/evidence updates. Existing durable-document deletion count is zero.
  User Guide behavior and shortcuts are unchanged; no guide rewrite is needed.
- Commit author/committer: existing owner identity `mc.kang`; attribution uses
  `Co-authored-by: ChatGPT <noreply@openai.com>`. Existing human commits were not
  rewritten. Any PR created for this slice is explicitly marked ChatGPT-assisted
  under the authenticated owner account `delphykmc`.

## Remaining work and acceptance

The first slice improves final preview paint, uint8 gain math and image-surface
drop dispatch. Folder Position still clears active Difference under the current
passive-selection contract; an explicit navigation continuation must preserve
pair/channel/ROI/generation/stale/shutdown ownership before changing that behavior.
Coordinated multi-view gain publication, repeated-key queue behavior, actual
network drop/decode and Explorer hover remain separate acceptance items. The
unreliable preliminary async gain probe is superseded by the event-loop probe;
neither establishes simultaneous monitor-visible publication.
No new human manual acceptance or real SMB validation has been performed.
