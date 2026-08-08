# Product specification

PixelScope is a CPU-only Windows engineering tool for rapid visual and numeric
comparison of PNG, BMP, JPEG, and profile-described RAW images. The workflow is
selection-driven rather than fixed A/B: register files or folders, select up to
six sources, inspect them in Single or Multi View, and compare full-image or ROI
results.

## Implemented workflow

- Folder-grouped Files tree with drag-and-drop, context actions, natural order,
  and loading/resident/error indicators.
- Ordered multi-selection and atomic Page Up/Page Down Folder Position navigation
  for one to six distinct registered folders.
- Up/Down retains Files-tree row navigation. Left/Right changes only the active
  image within the selected set; PageUp/PageDown changes selection membership by
  one registered Folder Position.
- Auto, Single, and Multi View with synchronized cursor, zoom, offset, ROI, and
  line coordinates.
- Fixed two/three/four/five/six-image layouts with primary-image ordering for
  every Multi View containing at least two images.
- The first displayed image is the implicit primary. Selecting another primary
  moves it to the first tile without changing Files selection order or logical
  image IDs.
- Two-, four-, and six-image layouts retain equal tile sizes; three- and
  five-image layouts enlarge the first, primary tile.
- Structured status for active file, format/resolution, coordinate, pixel value,
  zoom, and background work.
- Statistics with explicit image/channel fields and full-image/ROI scope.
- Histogram Auto/256/1024/4096 bins with Count, Normalized, and Log count.
- Horizontal/vertical Line Profile with explicit reference selection in
  Difference-from-reference mode. Reference priority starts with the primary
  image, then the active image, then the first displayed image.
- RGB and Bayer R/Gr/Gb/B analysis; RGBA alpha is ignored.
- Order-independent native absolute Difference cache with Absolute/Mask display,
  ROI metrics, LRU eviction, diagnostics, and a startup-configurable byte budget.
- Resizable, collapsible, floating, and maximizable Plots dock.
- Persisted main geometry, dock state, splitters, last directory, layout,
  analysis state, and selected Plots tab.
- `Edit > Settings...` uses **General / Files / Performance** category pages with
  a flat VS Code-inspired hierarchy.
- General owns the persistent RAW JSON confirmation preference, exact RAW
  file-size validation, and Difference Threshold/Gain defaults. RAW confirmation
  is not duplicated in the File menu.
- Exact RAW validation is propagated to the load worker/reader and to JSON
  sidecar auto-approval. Difference Threshold/Gain initialize at startup and
  apply to the live Difference panel after Settings saves without restart.
- Files provides optional Default Open Folder and Default Export Folder values.
  Blank preserves the remembered last-used-folder behavior; configured existing
  folders only seed dialog starting locations and apply without restart.
- Performance owns two independent startup budgets. **Decoded Source Memory**
  defaults to 256 MiB and accepts 128–2560 MiB; **Difference Map Cache**
  defaults to 128 MiB and accepts 64–1280 MiB. When physical RAM is known, their
  combined value must be no more than 50% of RAM; an invalid Save keeps the
  user's values visible. Unknown RAM uses product bounds only. This is a
  conservative configuration guard rather than OOM protection. Changes apply after
  PixelScope restarts and do not resize current runtime owners live.
- **Preload Next Folder Position** is enabled by default and is the third
  startup-only Performance setting. After foreground loading becomes idle,
  PixelScope decodes exactly the next Folder Position produced by the PageDown planner on
  a separate single-worker pool. It never scans unregistered siblings, preloads
  previous/next-next positions, or delays normal loading.
- Decoded Source Memory accounts native registered `ImageDocument.source` arrays
  only. The Files green residency indicator reflects this state, not Difference
  cache entries or total application memory.
- Source residency is a protected LRU soft budget. Visible, selected,
  active/analysis, current Difference-pair, and active load-target sources remain
  resident even when their bytes exceed the budget. Unprotected oldest sources
  are released and reload normally when required again; an oversized required
  source is not rejected or repeatedly load/evicted.
- Source eviction clears source-local Statistics/Histogram/channel-derived state
  but does not evict Difference maps solely because native source bytes were
  released.
- Valid preload results become ordinary decoded-source residents and receive no
  special protection. Stale/cancelled results and changed path/profile/generation
  identities are dropped; speculative failures remain silent and retryable.
- `Reset Settings` restores application preferences without resetting workspace
  layout, window geometry, dock/splitter state, or remembered last-directory
  state.
- Exact docking/layout values remain workspace state rather than configurable
  defaults because the saved workspace is already authoritative.

A seventh derived Difference result is shown in Single View when all six source
positions are occupied.

## RAW contract

RAW opens through a validated profile workflow. A same-name JSON sidecar can
pre-fill the profile; the General Settings preference may skip repeated
confirmation for those JSON profiles when the configured file-size policy also
matches. The RAW dialog's explicit don't-show-again choice updates only that one
typed preference and preserves the other schema-v3 settings. The same RAW path
may be reloaded with corrected settings.

When **Require Exact RAW File Size** is disabled, RAW files may contain trailing
bytes but may not be undersized. When enabled, the file byte count must exactly
match the selected profile's requirement.

The profile separates:

- storage format: unpacked, MIPI RAW10, RAW12, or RAW14
- sample container for unpacked data: `uint8` or `uint16`
- effective bit depth
- byte order and LSB/MSB alignment where applicable
- width, height, offset, stride, and grayscale/Bayer layout

Packed formats own their byte layout and fixed bit depth, so container,
endianness, and alignment controls do not apply. Bayer is analyzed as native
mosaic planes; demosaic is outside the current product contract.

## Future product scope

The complete product adds RAW demosaic/normalization/profile suggestion, alpha
overlay, persistent sessions
and ROI management, live GPU IQA/image evaluation, heatmaps, and a validated
standalone Windows distribution.
