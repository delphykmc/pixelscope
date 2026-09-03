# Execution plan: Reference/sample coordinates for subsampled views

Status: Active
Owner: ChatGPT-assisted implementation and independent reviewers
Branch/PR: `codex/issue-75-spatial-sampling` / stacked PR #76 targeting PR #74
Last updated: 2026-09-03

## Goal

Preserve native numerical arrays and sample cardinality while making cursor, zoom,
pan, ROI, line, and pixel interactions spatially align across full-resolution source
views and subsampled YUV or Bayer derived views. Completion is observed through a
reviewed stacked PR merged into PR #74, PR #74 ready for review, Issue #75 closed,
and the required automated and manual validation evidence recorded here.

## Scope

### In scope

- An explicit reference-space/sample-space presentation contract for native YUV
  chroma and Bayer split/Difference documents.
- Reference-space image presentation without allocating full-resolution numerical
  copies solely for display.
- Correct synchronized cursor, zoom/pan, ROI, line, and pixel lookup behavior.
- Regression tests and narrow durable documentation updates.

### Out of scope

- Chroma resampling as numerical authority or changes to native Difference metrics.
- New YUV color/range conversion behavior.
- Reinterpretation of Bayer CFA parity or source-domain analysis.
- Packaging work.

## Current state

PR #74 keeps YUV Difference maps at native Y/U/V plane resolution. The viewer in
`src/pixelscope/ui/image_viewer.py` currently uses the preview raster coordinate
system for its `ImageItem`, view range, pointer gestures, and overlays. Split and
Difference documents can therefore have a smaller preview raster than the source
reference extent. Issue #75 records the design problem and candidate mapping model.

## Invariants and constraints

- Target CPython 3.10 x64 and PyInstaller 5.7 `onedir` compatibility.
- Native source and Difference arrays, cache entries, metrics, exports, dtype, CFA
  parity, and YUV sampling semantics remain unchanged.
- Viewer rendering must not create a full-frame numerical copy solely to expand a
  subsampled plane.
- Numerical algorithms remain outside Qt widgets and expensive work stays off the UI
  thread.
- Existing user-owned untracked files and unrelated worktree changes are preserved.

## Proposed design

The Issue #75 decision record selects an immutable, Qt-free `SpatialSampling` value
attached as transient `ImageDocument` semantic metadata. `ImageDocument.shape`,
source/preview arrays, Difference cache entries, metrics, and exports remain in native
sample space; a separate reference shape governs viewer interaction.

`ImageDocument.pixel_at()` remains native-local. A structured reference lookup maps a
reference coordinate to an optional native sample coordinate/value. YUV chroma uses
`cell_footprint` floor/ceil mapping. Bayer channels use `point_lattice` with the
existing row/column CFA phase; non-matching sites have no numerical sample even when a
dense, phase-aware macrocell is painted for presentation.

`ImageViewer` owns only reference-space Fit/100%/hover/ROI/Line coordinates and
centrally applies an `ImageItem` rect/transform to the unchanged native preview.
`MultiCompareView` remains a representation-blind reference-space synchronizer.
Split/Difference producers declare mapping explicitly. Existing three-argument
Difference signals remain compatible while a typed mapping snapshot is bound to the
exact preview/cache identity and stored atomically with each derived result.

Spatial metadata is never serialized. Separately, PR #74's discovered Session-v1
compatibility gap is closed additively by allowing Y/U/V Difference recipe channels;
the schema and persisted fields do not change.

## Implementation slices

1. **Geometry contract**
   - Files/components: core document/presentation geometry and focused unit tests.
   - Observable result: subsampled derived documents declare reference extent and
     sample mapping without changing their native arrays.
   - Tests: direct mapping, phase, clamping, and unchanged full-resolution defaults.
2. **Viewer integration**
   - Files/components: image viewer and multi-compare interaction tests.
   - Observable result: native rasters occupy the full reference extent and shared
     interactions use reference coordinates.
   - Tests: cursor, view range, ROI, line, Fit, and 100% behavior.
3. **YUV and Bayer producers**
   - Files/components: split/Difference document construction and regressions.
   - Observable result: YUV422/420 and Bayer channel views carry correct geometry.
   - Tests: native shapes/cardinality plus reference-space alignment.
4. **Contracts and closeout**
   - Files/components: durable docs and completion evidence.
   - Observable result: system-of-record contracts match implementation.
   - Tests: documentation checks and full quality suite.

## Validation plan

- Targeted automated tests: core geometry, viewer interactions, WP-C1/WP-C2 YUV,
  Bayer split/Difference, ROI, line, cache/metric cardinality, and lifecycle tests.
- Full checks from `docs/QUALITY.md`: Ruff, formatting, mypy, full pytest, pip check,
  and documentation checks when Markdown changes.
- Manual Windows checks: YUV444/422/420 and Bayer mosaic/split/Difference hover,
  synchronized zoom/pan, ROI, line, Fit, and 100% behavior.
- Performance or memory checks: prove native arrays remain unchanged and no explicit
  full-resolution presentation array is allocated.

## Risks and mitigations

| Risk | Detection | Mitigation |
|---|---|---|
| Display transform changes existing full-resolution views | RGB/Gray/YUV444 viewer regressions | Identity geometry is the default contract |
| Bayer point phase is confused with YUV cell footprint | CFA channel mapping and ROI tests | Keep sampling semantics and phase explicit |
| ROI/line overlays are clamped to sample shape | heterogeneous-view interaction tests | Clamp shared interaction in reference space |
| Export or metrics consume presentation geometry | cache/cardinality/export regressions | Keep mapping metadata presentation-only |

## Progress log

- 2026-09-02: Confirmed PR #74 Draft at `b473127` and Issue #75 open with no prior
  comments; started three independent architecture, Bayer, and UX/performance reviews.
- 2026-09-03: Three reviews and two cross-reviews converged on explicit transient
  spatial sampling metadata, native-local `pixel_at()`, structured reference lookup,
  reference-space viewers, and distinct YUV-cell/Bayer-lattice semantics.
- 2026-09-03: Recorded the final ChatGPT-assisted implementation decision on Issue
  #75 and created stacked branch `codex/issue-75-spatial-sampling` from PR #74 HEAD.
- 2026-09-03: Implemented the Qt-free spatial contract, native YUV/Bayer producer
  metadata, reference-space viewer interactions, exact Difference mapping snapshots,
  and additive Session-v1 Y/U/V recipe vocabulary with focused regression coverage.
- 2026-09-03: Observed 62 focused tests passing, changed-file Ruff/format passing,
  `mypy src` passing, `pip check` passing, and the documentation contract passing.
  The owner-environment full suite completed with 1196 passed, 1 skipped, and one
  unrelated existing responsive-header assertion failure in
  `test_folder_display_tags_disambiguate_same_folder_and_file_names`; the changed
  coordinate/Difference paths had no failures.
- 2026-09-03: Manually verified YUV420 U split and U Difference native 8x6 rasters
  map their lower-right sample footprint to reference `(15, 11)` before/after zoom.
  Manually verified Bayer B point-lattice behavior at 95% zoom: reference
  `(960, 535)` has no B sample and adjacent `(961, 535)` reports `B 495`.
- 2026-09-03: Independent latest-head review of `a487163` requested changes for two
  production gaps: the composed Single View cursor handler re-read native-local
  coordinates, and non-cacheable Difference maps lost their already-published spatial
  snapshot. The reviewer independently confirmed the known TileHeader assertion is
  unrelated to this diff. Findings were recorded on stacked PR #76.
- 2026-09-03: Remediated both findings without changing the three-argument cursor or
  Difference signal contracts. Production-composed YUV/Bayer cursor regressions and
  cache-independent exact-payload mapping regressions now pass; independent re-review
  of the new HEAD remains pending.

## Completion summary

- Delivered behavior: implemented; independent latest-head review and merge are pending.
- Changed files: core spatial/document/channel-view contracts; viewer and Difference
  integration; Session recipe vocabulary; focused unit/UI tests; cumulative contract
  documents.
- Validation results: focused/static/docs/manual checks passed; full suite has one
  unrelated existing responsive-header assertion failure as recorded above.
- Remaining limitations: mapping is transient/presentation-only; no chroma resampling
  or new Session geometry is introduced.
- Follow-up issues: no deferred Issue #75 behavior; initial independent-review
  findings are remediated and await latest-head confirmation.
- Durable docs updated: `ARCHITECTURE.md`, `PRODUCT_SPEC.md`, `SESSION_CONTRACT.md`,
  `DECISIONS.md`, `QUALITY.md`, and `CURRENT_STATE.md`.
