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
- Order-independent Difference cache with native compact maps for equal effective
  bit depth and normalized float32 maps for mixed effective bit depth, plus
  Absolute/Mask display, ROI metrics, LRU eviction, diagnostics, and a
  startup-configurable byte budget.
- Resizable, collapsible, floating, and maximizable Plots dock.
- Persisted main geometry, dock state, splitters, last directory, layout,
  analysis state, and selected Plots tab.
- `Edit > Settings...` uses **General / Files / Performance** category pages with
  a flat VS Code-inspired hierarchy.
- General owns persistent RAW JSON confirmation, exact RAW file-size validation,
  and native Difference Threshold/Gain defaults. RAW confirmation is not
  duplicated in the File menu.
- Exact RAW validation is propagated to load worker/reader and JSON-sidecar
  auto-approval. Difference Threshold/Gain initialize at startup and apply to the
  live Difference panel after Settings saves without restart.
- Files provides optional Default Open Folder and Default Export Folder values.
  Blank preserves remembered last-used-folder behavior; configured existing
  folders only seed dialog starting locations and apply without restart.
- Performance owns two independent startup budgets. **Decoded Source Memory**
  defaults to 256 MiB and accepts 128–2560 MiB; **Difference Map Cache** defaults
  to 128 MiB and accepts 64–1280 MiB. When physical RAM is known, their combined
  value must be no more than 50% of RAM. Unknown RAM uses product bounds only.
  This is a conservative configuration guard rather than OOM protection.
- **Preload Next Folder Position** is enabled by default and is startup-only.
  After foreground loading becomes idle, PixelScope decodes exactly the next
  Folder Position produced by the PageDown planner on a separate single-worker
  pool. It never scans unregistered siblings, preloads previous/next-next
  positions, or delays normal loading.
- Decoded Source Memory accounts native registered `ImageDocument.source` arrays
  only. Files residency does not represent Difference cache or total process
  memory.
- Source residency is a protected LRU soft budget. Visible, selected,
  active/analysis, current Difference-pair, and active foreground-authority
  sources remain resident while required. Unprotected oldest sources reload
  normally when needed again; one oversized required source remains allowed.
- Source eviction clears source-local analysis/channel state but does not evict a
  valid Difference map solely because native source bytes were released.
- Valid preload results become ordinary decoded-source residents with no special
  protection. Stale/cancelled or identity-mismatched speculative results are
  dropped and failures remain retryable through normal loading.
- `Reset Settings` restores application preferences without resetting workspace
  layout, geometry, dock/splitter state, or remembered last-directory state.

A seventh derived Difference result is shown in Single View when all six source
positions are occupied.

## Difference contract

Difference compatibility is family-based: Gray compares only with Gray,
RGB/RGBA compares only with RGB/RGBA with alpha ignored, and Bayer compares only
with Bayer of the same CFA pattern. Cross-family, dimension-mismatch, CFA-mismatch,
and unsupported layouts are rejected; PixelScope performs no implicit RGB→Gray
conversion. Gray exposes `Gray`; RGB/RGBA exposes All/R/G/B; Bayer exposes
Mosaic/R/Gr/Gb/B.

Equal effective bit depths use the native code domain and preserve compact
uint8/uint16 absolute maps where applicable. Mixed effective bit depths
independently normalize each source by `(1 << bit_depth) - 1` and store the
absolute Difference as float32 in `[0,1]`. This normalization deliberately
ignores RAW Black/White levels, Display Gain/RAW Gain, display transforms,
preview values, and demosaic. Cache metadata records domain/data range so
reversed-pair reuse cannot change threshold or metric semantics.

Threshold uses `code` in the native domain and `%FS` in the normalized domain;
`1.00 %FS` means an internal threshold of `0.01`, and mask comparison remains
strict `>`. Persisted Settings Threshold remains the native-domain code default
under schema v5. Normalized threshold starts at `1.00 %FS` and is session-local.

## Display-gain contract

P3-B introduces one generic presentation primitive:

```text
display = anchor + gain * (source - anchor)
```

The numerical core is not RAW-specific. It accepts a caller-supplied scalar
anchor, naturally supports `anchor=0`, uses float32 affine processing, and may be
applied to selected channel views. It never modifies native source data.

P3-B product activation is intentionally narrower than the core capability:

- only RAW viewer presentation exposes gain in P3-B;
- the current control is named **RAW Gain**;
- ordinary PNG/BMP/JPEG Gray/RGB/RGBA presentation remains unchanged;
- the generic core is prepared for P3-C reuse rather than exposing an unfinished
  ordinary-image feature in P3-B.

Display gain is always presentation-only. Pixel inspection, Statistics,
Histogram, Line Profile, Difference, generation, source residency, and cache
identity remain independent of it.

## RAW contract

RAW opens through a validated profile workflow. A same-name JSON sidecar can
pre-fill the profile; the General Settings preference may skip repeated
confirmation for those JSON profiles when configured file-size policy also
matches. The RAW dialog's explicit don't-show-again choice updates only that one
typed preference and preserves other schema-v5 settings. The same RAW path may be
reloaded with corrected settings.

When **Require Exact RAW File Size** is disabled, RAW files may contain trailing
bytes but may not be undersized. When enabled, file byte count must exactly match
the profile requirement.

The profile separates:

- storage format: unpacked, MIPI RAW10, RAW12, or RAW14;
- sample container for unpacked data: `uint8` or `uint16`;
- effective bit depth;
- byte order and LSB/MSB alignment where applicable;
- width, height, offset, stride, and grayscale/Bayer layout;
- `black_level` and `white_level` metadata, including R/Gr/Gb/B Black tuples for
  Bayer profiles.

Decoded samples in `ImageDocument.source` are the native RAW authority. Pixel
inspection, Statistics, Histogram, Line Profile numerical data, Split Channels,
P3-A Difference, and source residency operate on those native samples regardless
of viewer gain.

RAW display is explicitly separate from analysis:

- at `RAW Gain = 1×`, display range is native code
  `0..((1 << bit_depth) - 1)`;
- `black_level` is not subtracted from 1× display and `white_level` is not used as
  display maximum;
- gained RAW uses the generic display-gain formula with a Black-derived anchor;
- RAW Gray scalar Black is the scalar anchor;
- schema-valid GRAY four-value Black remains compatible and uses legacy
  `min(black_level)` as the global display anchor;
- Bayer tuple Black uses CFA-specific R/Gr/Gb/B anchors; scalar Bayer Black applies
  one anchor to all channels;
- Bayer anchor processing does not create a full-size Black map;
- gain/range mapping uses float32 fused affine processing where possible and
  clipping occurs at final display conversion;
- `white_level` remains metadata only in the P3-B display contract;
- RAW Gain is session-local, shared across visible RAW Single/Multi View tiles,
  and is not a Settings/profile persistence field.

Gain 1× reuses the canonical document preview. Gain >1 regenerates only derived
viewer presentation from resident source on the shared numerical worker pool.
Gain changes do not reload/decode native RAW, change source residency ownership,
bump source generation, or change Difference cache identity. Hidden viewers
release gain>1 derived buffers and regenerate current gain when shown again.

Packed formats own their byte layout and fixed bit depth, so container,
endianness, and alignment controls do not apply. Bayer is analyzed as native
mosaic planes. Demosaic, white balance, CCM, tone mapping, and processed-RAW
analysis are outside the current product contract.

## Future product scope

P3-C will extend the P3-B generic gain core to ordinary Gray/RGB/RGBA viewer
presentation:

- ordinary Gray/RGB use `anchor=0`;
- RGBA applies gain to RGB and preserves alpha;
- user-facing naming is **Display Gain** or **Gain**, not Exposure;
- 1× remains identity/no-work where possible;
- clipping is deterministic and presentation-only;
- source and Statistics/Histogram/Line Profile/Difference semantics remain
  unchanged;
- regression scope includes 1× identity, clipping, Gray/RGB/RGBA behavior, alpha
  preservation, and analysis independence.

P3-C may also improve RAW clipping/Bayer observability. Later planned work includes
reusable RAW profile management and deterministic profile suggestion, alpha
overlay, persistent sessions and ROI management, live GPU IQA/image evaluation,
heatmaps, and a validated standalone Windows distribution.

Demosaic remains deferred unless a future owner-approved processed-preview scope
defines the associated white balance, color, tone, metadata, and analysis
boundaries coherently.
