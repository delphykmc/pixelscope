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

## P1-D — workspace completion and cleanup

- Independent floating Plots geometry persistence.
- Floating title-bar double-click maximize/restore.
- Final Esc/Shift+Esc naming and regression coverage.
- Removal of the obsolete fixed-arrangement compatibility field and QSettings
  key.
- Preserve and test the already implemented selected-tab persistence.

See `docs/exec-plans/active/next-phase.md`.

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
