# UX-3E E1 — Native IQA acceptance matrix

Status: **draft public-safe Handoff QA protocol**, not PRIVATE SUB acceptance.
Baseline: `handoff/enterprise-iqa-window@5441b102c902fced0361758dbd1fc69e4ee2bc63`
(PR #166 UX-3C squash). Issue #168 / #153 / #141.

The E1 slice verifies actual Qt lifecycle and operator-visible behavior. It does
**not** claim that a dummy portable Result is production validated, that private
server requests succeed, that a corporate package exists, or that a second
physical screen can be simulated by running Qt offscreen.

## 1. Native focused Windows gate

Use Windows Python 3.10 / PySide6 in the Handoff E1 branch. Run in a dedicated
pytest process with **normal cyclic GC** and the project's existing installed
Qt dependencies. Do not add full native Qt pytest to generic hosted PR CI.

```powershell
git switch feat/168-enterprise-iqa-ux3e-e1-native-acceptance
git pull --ff-only
$env:PYTHONPATH = "src"

& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_iqa_ux3e_native_acceptance.py
```

Run existing integration tests **in a separate process** to keep native Qt
teardown classes from interacting:

```powershell
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_iqa_ux3c_delivery.py `
  tests/enterprise/iqa/test_iqa_composition.py
```

Optional real MAIN host gate (third process):

```powershell
$env:PIXELSCOPE_RUN_IQA_REAL_HOST = "1"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_iqa_composition_main_window.py
Remove-Item Env:PIXELSCOPE_RUN_IQA_REAL_HOST -ErrorAction SilentlyContinue
```

E1 native regression coverage:
- Repeat show/hide/close/reopen with **one** AnalysisWindow per manager, then
  idempotent explicit manager shutdown and normal `gc.collect()`.
- Quiesce an intentionally unfinished synthetic spatial Future and QTimer on
  shutdown; do not run a synthetic heavy CPU benchmark inside the Qt lifecycle
  test. No stale UI callback should run.
- Restore a deliberately off-screen stored geometry; the resulting window must
  intersect an available Qt screen by at least 100×100 source-independent pixels.
  This is **not** a substitute for an actual unplugged/moved monitor test.

If a Windows access violation is encountered, run each failing native test in
its own **fresh process**; report the exact invocation, Windows/PySide6 versions,
stack trace and whether the failure occurs **during test body or interpreter
teardown**. Do not silence a native crash by blanket deselection.

## 2. Manual monitor/DPI layout matrix

Record **PASS/FAIL/NOT RUN** and physical hardware for each row. Do not claim
real dual-screen or per-monitor DPI coverage from generic Windows GitHub CI.

| Viewport / DPI | Actual physical check | Assertions / screenshots |
| --- | --- | --- |
| FHD 1920×1080 at 100% | Owner Windows | A/B/Map labels readable, Inspector chart visible and independently resizeable; Jobs Dock does not force disappearing image viewport |
| FHD at 150%, if available | Owner Windows | Same, no clipped toolbar/Cancel/ROI controls, dock can be hidden |
| UHD 3840×2160 at 150–200% | Owner Windows | 4K pair aligned, map/grid valid, dock resize, legible scale legends |
| Secondary display connected | Owner Windows | First Analysis Window opens on expected secondary screen, geometry saved |
| Secondary display disconnected / resolution reduced | Owner Windows | Reopen within visible primary screen and preserve usable sizes |
| Mixed DPI monitor transfer | Owner Windows | Move window, hide/reopen, no panel overflow or lost floating dock |

Suggested synthetic manual UX entrypoints:

```powershell
& $py -m pixelscope_enterprise.iqa.demo --rgb
& $py -m pixelscope_enterprise.iqa.host_preview --rgb
```

## 3. Operator journey / negative paths

1. Open independent window with no job; file **Open Result** and **Save Result
   As** stay disabled without trusted loader/writer (#140), while genuine
   CSV/PNG/HTML export is separately offered for an in-memory result.
2. Inspect 4K synthetic A/Map/B; change attribute and crop/ROI; zoom/pan and
   ROI stay synchronized without confusing **OFFICIAL FULL PAIR** and
   **GRID-DERIVED ROI** numeric values.
3. With synthetic RGB absent, A/B panes accurately indicate unavailable
   source; spatial map/statistics remain accessible where supplied.
4. Run synthetic host job #1: status cue remains visible while Jobs Dock is
   hidden, but **completion never auto-opens** Analysis Window; user explicitly
   selects **View selected result**. Job #2 fails, job #3 requires an actual
   Cancel request and reports cancelled only after worker acknowledgment.
5. Trigger Hotspot Candidate scan then close/hide/reopen Analysis Window;
   verify no indefinitely busy indicator, stale ROI card or native crash.
6. Export CSV, PNG and offline HTML from synthetic data; confirm clear
   provenance labels and **no network fetches**. Do not confuse Export with
   portable Result Save As.
7. Repeat open/close and final MAIN shutdown; review Window Manager ownership,
   secondary monitor state, busy spatial scan and Qt GC behavior.

Record hardware, Windows build, Python/PySide6/pyqtgraph versions, branch SHA,
native pytest summaries and any screenshot evidence links. Use synthetic
paths and screenshots only; do not commit private IQA inputs, logs with
credentials, user home paths or proprietary result schemas.

## 4. Remaining UX-3E and other gates

**E2 (separate reviewed PR/gate):** coordinate with #156 U2 (downstream-owned
build descriptor), U3/U11 (manifest/immutable SHA/import lineage) and U9
(runtime dependencies/entrypoint). Pin the **final** approved Handoff SHA,
produce allowlisted path/digest/deletion evidence, prove SUB sibling files are
not overwritten, and verify an authorized PRIVATE SUB package. The initial
Handoff E1 baseline SHA above is **not yet an E2 approval pin**.

**UX-3D (#140):** only enable true portable offline Open/Save As after an
approved sanitized versioned manifest/NPZ reader/writer with READY/digest/size,
dtype/shape/path confinement and roundtrip fixtures. E1 intentionally
does not implement this.

**Backend nonblocking follow-ups:** authoritative result readiness before
terminal completed snapshot, explicit asynchronous cancel-rejection/retry
acknowledgment, operator-visible cancellation submission failure and bounded
shutdown when real callbacks race. Actual auth/job correlation remains SUB-owned.

**Branch rules:** all code/tests/docs in Enterprise reserved IQA paths;
squash merge reviewed E1 into `handoff/enterprise-iqa-window` only. PUBLIC
MAIN/Reference must stay unchanged. Do not close #153/#145/#141 until their
remaining release/portable/transfer criteria are met.
