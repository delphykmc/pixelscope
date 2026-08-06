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

- Show the pin/order control in every Multi View with two to six displayed
  documents.
- Define pinning as promotion to the first tile while preserving Files selection
  order and logical image IDs.
- Keep enlarged first-tile geometry only for three and five views; two, four,
  and six views retain equal tile sizes.
- Replace focus-only tooltip terminology with first-tile/order terminology.
- Make Split Channels transitions from Bayer/RGB channel planes to unsplittable
  GRAY content visually atomic.
- Preserve loading placeholders, viewer reuse, Difference priority, synchronized
  view state, and channel-split action state.

## P1-E — Plots workspace completion

- Independent floating Plots geometry persistence.
- Floating title-bar double-click maximize/restore.
- Final Esc/Shift+Esc naming and regression coverage.
- Preserve and test the already implemented selected-tab persistence.

## P1-F — fixed-layout compatibility cleanup

- Remove the obsolete fixed-arrangement compatibility registry, field, actions,
  and QSettings key.
- Replace arrangement-dependent startup, reset, and six-source Difference
  restore paths with the single fixed-layout policy.
- Preserve exact one-to-six geometry and restored workspace state.

See `docs/exec-plans/active/next-phase.md` for P1-D through P1-F.

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
