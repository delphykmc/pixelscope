# Enterprise IQA Window — temporary public-safe handoff

Tracking: [#141](https://github.com/delphykmc/pixelscope/issues/141). Implementation branch: `feat/141-analysis-window-shell` targeting **`handoff/enterprise-iqa-window`, not `main`**.

## Integration provenance

| Field | Value |
|---|---|
| Current approved merged MAIN / handoff pin | `95b7845e731302934e21033a0ee09ef08947495a` (merged PR #143) |
| Previous pre-#143 development pin | `e8959eaa27acc0777542f33a8bf476e3ec6ad28c` (merged docs PR #142) |
| Original #144 full-history backup | `archive/141-pre-143-rebase-20261009` at `1c67025cb836014335958ffd73232bf999efb8c1` |
| Public IQA contract revision at base | `IQA_PUBLIC_CONTRACT_REVISION = 1` |
| MAIN host implementation | #139 implemented by **merged PR #143**, now included in this handoff baseline |
| Server output contract | #140 **proposal**, not a finalized file schema |
| Public-safe branch disclosure | All branch files and commits are publicly readable |
| Ownership | Only `src/pixelscope_enterprise/**`, `tests/enterprise/**`, `docs/enterprise/**`, `enterprise/**` |
| Merge prohibition | Do **not** merge any Enterprise path into public `main` |

PR #143 merged into MAIN on **2026-10-09**. The current handoff base is the
verified merge commit above; the public contract revision remains `1`.
To avoid rewriting 59 commit-by-commit review steps with remote-only GitHub API
access, the feature's **exact eight final blob versions** were transplanted
onto that MAIN commit in a single squash-rebase commit, preserving the
original unmerged history on the archive branch. The PR still targets
`handoff/enterprise-iqa-window`, **never public MAIN**. This base pin is
complete, but PRIVATE SUB transfer and runtime validation remain separate gates.

## Implemented preliminary standalone window scope

- One extension-owned, independent non-modal `QMainWindow`, managed as a singleton,
  initially placed on the secondary screen when present. Last geometry is stored under
  a separate company-neutral Enterprise UI settings identity; disconnected-screen
  geometry is rejected in favor of an on-screen fallback.
- Empty opening supported; file **Open/Save As** actions are disabled until a real
  versioned, verified file reader/writer is injected. Result presentation itself
  is strictly user-directed, not triggered by a background job.
- Three source-pixel-coordinate A/B/Map views with shared zoom/pan and Shift+drag ROI.
  Source RGB absence retains official and spatial results. A spatial image uses the
  declared grid geometry and is rendered at grid resolution, not upsampled to 4K.
- Attributes appear in supplied order with unit/group identification, explicit
  official pair comparison and separate **GRID-DERIVED** ROI mean plus valid coverage.
  Missing and failed values are displayed as absent, never silently as numeric zero.
- Attribute/result selection retains ROI, attribute, map range and navigation state
  per result in memory. Fixed symmetric range defaults come **from the adapter**;
  manual range changes affect colors and clamp counts only, not numeric summaries.
- Semantic direction `positive = A better` is not guessed: the adapter must supply
  already quality-oriented values and set `quality_oriented` only where authoritative.
  Neutral metrics explicitly do **not** claim a winner.
- No company-specific code, URLs, paths, payloads, model algorithms or private data.

## PR #144 independent-review follow-up

- **P1 polarity fixed:** verified quality-oriented values use red/blue with an
  explicit `+A-better/-B-better` legend. Non-oriented signed values use an
  independent purple/teal palette labeled **positive/negative signed polarity
  only**, with no quality winner. Missing/masked cells remain transparent.
  Vectorized NumPy conversion replaces nested per-cell Python/Qt calls.
- **P1/P2 immutable Result ID guard:** reusing an ID with a different
  `AnalysisResult` object raises `ValueError` **before** changing visible
  state or RGB cache. This intentionally rejects even a second equivalent
  in-memory instance: H2 must deduplicate by validated scientific identity
  (or explicitly assign a new Result ID) rather than silently overwrite.
  Re-selecting the same instance is allowed and preserves its UI state.
- **H2 view-state seam:** injected `ResultLoader` now returns
  `LoadedAnalysis(result, analysis_state)`. Saved state is validated for
  declared attributes, known fixed ranges, source-bound ROI and finite,
  bounded viewport values **before** UI mutation. Saver continues receiving
  a separate view-state dictionary. A real secure portable file codec,
  result integrity, versioning and saved-file round-trip remain H2 deliverables,
  **not** implemented by these callback contracts.
- **Regression scope:** signed/quality color, 64k-cell vectorized map,
  immutable ID/attribute/source collision, state restoration and invalid
  ROI/attribute rejection are covered by newly authored tests.
- **Environment gate:** changes are subject to repo CI Ruff/mypy checks.
  Existing change-scoped Windows job skips `tests/enterprise/**`. A
  supported Windows Python 3.10/PySide6 6.4.2 focused run and native Qt/GC
  repeated open-close smoke are still mandatory before accepting the slice.
  Do not equate general screenshot CI with this dedicated UI validation.

## Owner Windows validation — 2026-10-09 (PR #144)

Owner environment: Windows, Python 3.10.11, PySide6/Qt 6.4.2.
At former HEAD `34e2294a`: pure model **10 PASS**; window test **7 PASS /
1 FAIL**, with three remaining tests not executed by `pytest -x`. The
reproducible failure was `test_saved_analysis_state_validation_and_restoration`
because the window wrote viewport center `(-154.6667,-288.0)` before the
views were laid out, yet its reader rejected off-image coordinates. Manual
demo also reported a tiny map, dead wheel zoom and non-working Shift+drag.

### Corrective design

- First source-pixel fit is deferred with a zero-delay Qt event-loop callback
  until the window is visible and its three viewports have real sizes. A
  bounded retry handles late splitter geometry. No fit or synthetic navigation
  state is persisted for a result prepared **before show**.
- Post-show fit uses the canonical source center, and wheel minimum zoom is
  relative to the fitted scale rather than a hard `0.04` cutoff. This permits
  meaningful zoom with a large 4K source and maintains linked-view navigation.
- A finite, bounded off-image viewport center (e.g. an oversized viewport
  around a small 128-pixel image) can be restored. Arbitrarily large,
  non-finite or unreasonable coordinates and invalid zoom remain rejected.
- Shift+drag in the actual graphics **viewport** provides a mouse-transparent
  rubber-band preview, then sets a source-bounded ROI overlay on all three
  views. Attribute switching preserves the ROI.
- Focused tests now exercise the previously failing pre-show round-trip, a
  visible-window viewport wheel event on synthetic 4K data, a real
  Shift-modified mouse drag on the map, drawn overlay and attribute
  persistence, and bounded visible-state restore/reject behavior. Direct
  `_set_roi` tests are no longer the only ROI evidence.

These are **implemented corrections, not yet an owner-verified Windows pass**.
Re-run the entire focused suite without `-x` after this fix and inspect the
standalone GUI. The change-scoped CI does not run Enterprise Qt tests.

## Owner 14/14 Qt PASS and ROI usability review (2026-10-09)

The owner reran the Windows 3.10.11 / PySide6 6.4.2 Enterprise Qt
test module against the prior HEAD `5a609023`: **14 passed**, with five
`QMouseEvent.pos()` deprecation warnings. This confirms the previously
reported initial fit / wheel zoom / pan / viewport restore blockers were
resolved on that HEAD. The owner subsequently observed **persistent
visual outlines after repeated Shift+drag ROI**, even though each scene
had one current ROI geometry item. Passing the earlier single-ROI unit
test did *not* verify the stale viewport pixels.

Follow-on changes in this slice (new owner Windows validation required):

- Each completed ROI selection discards its `QRubberBand` child geometry and
  explicitly repaints the affected viewport. Updating or clearing a ROI
  also performs an on-demand viewport repaint across A/B/Map. This is
  discrete-event invalidation, **not** a continuously enabled
  `FullViewportUpdate` mode on every pan/zoom.
- The finalized overlay is visible on Spatial Map only when a spatial
  grid exists. It is mirrored on Source A and/or B **only when their
  original RGB images were successfully loaded**. Synthetic source
  absence is an expected state, not a server error. One authoritative
  ROI in image coordinates is retained even if images are unavailable.
- Shift selects with a crosshair rather than a hand cursor regardless
  of which Inspector sibling has focus; releasing Shift / losing focus
  restores the navigation cursor.
- Standalone **View > Clear ROI**, an Inspector **Clear ROI** button and
  shortcuts `Esc` / `Shift+Esc` delete only the active Result's ROI
  and any in-progress rubber-band selection. The shortcut convention is
  `Esc` for ROI; the alias is provided for owner discoverability.
- Inspector now displays **ROI source (x,y,w,h)**, selected source-pixel
  area and area-weighted grid valid/total coverage plus **GRID-DERIVED**
  mean where available. Never equate this with the separate
  **OFFICIAL full-pair** metric.
- Deprecated Qt mouse `pos()` is replaced with
  `position().toPoint()`. Qt-focused tests now include repeated real
  viewport Shift+drag, painted-pixel old-outline disappearance **without
  a resize**, explicit clear, source A/B present/missing combinations,
  per-result retention, key modifiers and ROI quantitative context.

The new interactive tests **have not yet been run by the owner on
Windows**. Rerun the *entire* focused Qt module including a strict
`-W error::DeprecationWarning` check when practical. Dual-monitor/DPI,
native GC repetition and packaging remain gates. No `main` branch
or Reference UI changes should be imported with this patch.

## Owner Windows focused test follow-up — attribute switch / missing map

On Windows (Python 3.10.11 / PySide6 6.4.2), the owner ran model tests
**10 PASS** and the strict-deprecation Qt suite **16 PASS / 1 FAIL**
(17 total) at the preceding PR #144 HEAD. The failure was
`test_roi_source_panels_only_when_rgb_exists_and_stats_include_pixel_area`:
after calling `attribute_table.selectRow(1)` (attribute without a
spatial grid), the Spatial Map ROI rectangle remained visible.

The visibility predicate in `_draw_roi()` already checks the selected
attribute's `spatial` field. The selection handler had instead read
`currentRow()` from an `itemSelectionChanged` callback, which can be
stale during programmatic row changes. It now obtains the actually
selected row via `selectionModel().selectedRows()` and enforces
single-row selection. Regression assertions verify that selected
`attribute_id` changes as intended and map-ROI visibility toggles
on repeated attribute switches while image-source visibility and ROI
coordinates remain intact.

**This is a code-level correction, not yet a confirmed rerun of the
failed Windows test.** The full module should be executed again in the
owner environment; existing change-scoped CI still skips Enterprise Qt.

## Manual standalone preview

In a normal project Python 3.10 environment with editable package and Qt dependencies:

```powershell
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"  # optional: automated/headless smoke only
python -m pixelscope_enterprise.iqa.demo
```

The demo synthesizes 12 public-safe attributes and an aligned 3840×2160/64 spatial
grid. RGB source files are intentionally absent, making the numeric/map fallback
observable. The synthetic official values do **not** establish scientific
equivalence to a model or server output. For visual inspection on a real screen,
omit `QT_QPA_PLATFORM=offscreen` (PowerShell: `Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue`).

Focused validation (run in the MAIN-compatible Python 3.10 Qt environment):

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q tests/enterprise/test_analysis_model.py
# Run Qt tests in a *separate Python process* to isolate native Qt teardown.
.\.venv\Scripts\python.exe -m pytest -q tests/enterprise/test_analysis_window.py
```

The authoring environment does **not** have PySide6 and cannot execute these
native Qt tests. Latest owner evidence: **10 model PASS; 16 window PASS / 1
window FAIL**, from the strict-deprecation 17-case Qt module at the previous
head. The remaining failure (selected attribute/map overlay visibility)
has a targeted fix using the selection model's selected row; no subsequent
owner Qt rerun has been reported. **Rerun both suites** on the rebased head,
including real keyboard/ROI and normal cyclic-GC GUI smoke. Repo CI
Ruff/typecheck success cannot substitute for this Windows native check.

## Explicit follow-up / owner integration gates

1. **#139 MAIN host — BASELINE DONE, INTEGRATION PENDING:** merged PR #143
   supplies the generic menu/dock/status/window lifecycle, including optional
   IQA command group and View-managed mock jobs/analysis-child visibility.
   The handoff and Enterprise feature are rebased against exact MAIN merge
   SHA `95b7845e731302934e21033a0ee09ef08947495a`. The production
   Enterprise contribution still must integrate with the existing
   `WindowContribution` phases and run owner Windows Qt lifecycle tests.
   Introduce no IQA-specific API in Base. Real job scheduling, completion
   notifications, validation, polling and result-view actions remain
   extension-specific follow-on work.
2. **#139 MAIN public semantic gap (conditional):** existing public `IqaResult`
   primarily exposes per-variant summaries; it lacks an authoritative first-class
   pairwise *official relative* result. The downstream `AttributeDisplay` boundary
   temporarily decouples the UI. Decide only after sanitized #140 schema/fixture
   shows if a small additive public pair-comparison contract is required. Do not
   infer official scores from grid means or rounded per-image dB.
3. **#140 server contract:** provide normalized, validated per-attribute signed
   grids, official comparison semantics, masks, geometries and a portable immutable
   artifact. H2 reader/writer must validate versions, hashes, sizes, compression,
   array dtypes, path confinement and reject pickle. File handlers remain disabled
   until real round-trip tests exist.
4. **Follow-on window slices:** a real grouped bipolar chart, cursor crosshair,
   finer drag ROI feedback, sliding-window hotspots, image/CSV/HTML exports, persisted
   analysis state in Save As, DPI/4K performance measurements, multiple monitor
   lifecycle and stale-worker verification. Current attribute table is a functional
   interim inspector, not the final 10–12 metric chart.
5. **Transfer:** after review and validation, import only allowlisted SUB-owned
   paths from the pinned handoff SHA into PRIVATE SUB. Verify commit/path manifest and
   tests there. Do not cherry-pick or merge the public Enterprise branch into MAIN;
   remove the temporary branch only **after** proven transfer. Keep private adapters
   and config exclusively in PRIVATE SUB.

## Completed MAIN #143 baseline transplant (2026-10-09)

1. Verified #143 merged with exact MAIN `95b7845e731302934e21033a0ee09ef08947495a`
   (main parent of the new commit; PUBLIC contract revision `1`).
2. Saved former #144 HEAD `1c67025cb836014335958ffd73232bf999efb8c1`
   to `archive/141-pre-143-rebase-20261009` **before** rewriting any ref.
3. Created a Git tree from the approved MAIN tree and copied only the eight
   previously verified Enterprise-owned final **blob SHAs**. This is a
   *squashed rebase*, not a replay of the 59 historical commits; all old
   commit details remain accessible through the archived branch.
4. Created a new feature commit with sole parent the exact merged MAIN SHA,
   then advanced `handoff/enterprise-iqa-window` to that MAIN SHA and
   moved `feat/141-analysis-window-shell` with force-with-lease after
   verifying expected old ref values. Both refs were updated successfully.
5. Re-checked MAIN...Enterprise diff: **eight added Enterprise files only**,
   no modifications to `src/pixelscope/**`,
   `src/pixelscope_iqa_reference/**`, `tests/iqa_reference/**` or public
   general docs. This document receives a subsequent Enterprise-only update.
6. Current PR #144 remains Draft and targets the handoff baseline, **not MAIN**.
   Rerun static/typecheck/docs workflows on final HEAD, then owner Windows
   model/Qt tests and interactive GUI validation before PRIVATE SUB import.

Since history was intentionally squashed, do **not** run the obsolete
`git rebase --onto ... e8959eaa` command against the current feature.
Fresh local clones/worktrees should fetch the rewritten Enterprise ref
and, if needed, branch anew from the updated remote feature. Preserve the
archive ref until the PRIVATE SUB transfer is verified.
