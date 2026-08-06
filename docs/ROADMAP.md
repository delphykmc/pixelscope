# Roadmap

## Delivered baseline

### Local inspection and comparison

- PNG/BMP/JPEG and profile-described RAW loading.
- Source-preserving pixel inspection and display conversion.
- Ordered selection, folder navigation, fixed one-to-six-image layouts,
  synchronized cursor/range, shared ROI, and line selection.
- Statistics, Histogram, Line Profile, Difference, and structured status.
- Difference LRU cache, chunked native metrics, and reloadable source residency.
- Persisted workspace geometry, dock state, splitters, layout, analysis state,
  and selected Plots tab.

### RAW workflow

- Unpacked `uint8`/`uint16` with effective bit depth, endian, stride, offset,
  and LSB/MSB alignment.
- MIPI RAW10, RAW12, and RAW14.
- Grayscale and Bayer mosaic analysis.
- JSON profile load/save, legacy migration, confirmation preference, and
  deterministic fixture coverage.

## P1-D — Multi View ordering and Split transition polish

Status: Complete, validated, and merged as PR #10.

- Show a primary flag in every regular Multi View with two to six displayed
  documents.
- Treat the first displayed image as the implicit primary until another primary
  flag is selected.
- Promote the selected primary to the first tile while preserving Files
  selection order, logical image IDs, viewer reuse, and synchronized ranges.
- Keep equal tile sizes for two, four, and six images. Three- and five-image
  layouts enlarge the first, primary tile.
- Use primary-image terminology in tooltips, status text, product documentation,
  and reference-priority descriptions.
- Keep Split Channels component ordering fixed and hide primary flags for
  transient `CHANNEL_*` tiles.
- Make Split Channels transitions from Bayer/RGB channel planes to unsplittable
  GRAY content visually atomic.
- Keep Page Up/Page Down folder-pair navigation owned by MainWindow application
  shortcuts while supporting focus in the Files view or visible image tiles.

## P1-E — Plots workspace completion

Status: Complete, validated, and merged as PR #11.

- Independent floating Plots geometry persistence.
- Floating title-bar double-click maximize/restore.
- Final Esc/Shift+Esc naming and regression coverage.
- Preserve and test the already implemented selected-tab persistence.

## P1-F — fixed-layout compatibility cleanup

Status: Implemented in the current scoped PR; pinned local validation and manual
Windows checks remain before merge.

- Remove obsolete arrangement constants, registry, runtime fields, menu/actions,
  setter, startup/save, render, and restore paths.
- Ignore legacy `ui/multiview_arrangement` values at startup, never save the
  key, and remove it during workspace reset.
- Keep `_fixed_geometry()` as the sole fixed one-to-six layout policy.
- Preserve primary ordering, logical identity, synchronized ranges, Split
  Channels behavior, and exact six-source Difference restoration.

P1-D through P1-F complete the workspace-polish program. See
`docs/exec-plans/active/next-phase.md` for the completion record. No additional
phase is introduced by P1-F.

## P2 — performance controls and diagnostics

- Preferences UI with restart-applied performance settings.
- Byte-budgeted decoded-image residency.
- One-group-ahead folder preload with bounded cancellation.
- Worker/cache/load diagnostics and failure visibility.

## P3 — workflow depth

- Recent files, saved ROI manager, persistent comparison sessions.
- Arbitrary-angle line sampling, alpha overlay, and additional export formats.

## P4 — RAW processing depth

- Demosaic preview with explicit algorithm, memory, cache, and UX policy.
- Black-level subtraction and white-level normalization.
- RAW profile suggestion and reusable profile management.

## P5 — remote IQA

- FastAPI GPU server, PyTorch worker, asynchronous queue/cancellation.
- Artifact download, heatmap overlay, and evaluation comparison.

## P6 — distribution

- PyInstaller 5.7 `onedir`, portable ZIP, Inno Setup.
- Clean-PC smoke tests, code-signing review, GitHub Release update checking,
  and update strategy.
