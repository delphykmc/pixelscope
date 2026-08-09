# Product specification

PixelScope is a CPU-only Windows engineering tool for rapid visual and numeric
comparison of PNG, BMP, JPEG, and profile-described RAW images. The workflow is
selection-driven rather than fixed A/B: register files or folders, select up to
six sources, inspect them in Single or Multi View, and compare full-image or ROI
results.

## Implemented workflow

### Image registration

PixelScope exposes one file-opening command, **Open Images...**, and one folder
command, **Open Folder...**. The exact file contract is:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The file picker displays `Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)`.
There is no separate top-level RAW-open command and unsupported extensions are not
silently interpreted as RAW.

Folder discovery and drag/drop use the same supported input family. `.json`
sidecars are metadata for same-basename RAW inputs and never appear as independent
image entries. Files are grouped by parent folder with natural order and
loading/resident/error indicators.

Ordinary PNG/BMP/JPEG inputs register directly for ordinary decoding. A RAW input
must resolve a validated profile first:

- same-basename sidecar present: parse/validate it and preserve the current
  confirmation and exact/minimum-size policy;
- no sidecar: open the editable RAW Profile dialog;
- invalid sidecar: warn and open editable fallback instead of applying invalid
  metadata;
- cancelled profile dialog: do not register that RAW document;
- multi-file RAW open: resolve each selected RAW independently.

The product does not automatically reuse the previous RAW profile, apply one
profile to all selected RAW files, or pick a profile from byte size alone.

### Workspace and analysis

- Ordered multi-selection and atomic Page Up/Page Down Folder Position navigation
  for one to six distinct registered folders.
- Up/Down retains Files-tree row navigation. Left/Right changes only the active
  image within the selected set; PageUp/PageDown changes selection membership by
  one registered Folder Position.
- Files-tree `+` / `-` retains Qt-native folder expand/collapse. Display Gain
  `+` / `-` is scoped to the image-presentation subtree.
- Auto, Single, and Multi View with synchronized cursor, zoom, offset, ROI, and
  line coordinates.
- Fixed two/three/four/five/six-image layouts with primary-image ordering.
- Structured status for active file, format/resolution, coordinate, pixel value,
  zoom, and background work.
- Statistics with explicit image/channel fields and full-image/ROI scope.
- Histogram Auto/256/1024/4096 bins with Count, Normalized, and Log count.
- Line Profile with primary→active→first-displayed reference priority in
  Difference-from-reference mode.
- RGB and Bayer R/Gr/Gb/B analysis; RGBA alpha is ignored.
- Order-independent Difference cache with native compact maps for equal effective
  bit depth and normalized float32 maps for mixed effective bit depth, plus
  Absolute/Mask display, ROI metrics, LRU eviction, diagnostics, and a
  startup-configurable byte budget.
- Resizable/floating Plots dock with persisted workspace state.

A seventh derived Difference result is shown in Single View when all six source
positions are occupied.

## Settings and runtime policy

`Edit > Settings...` uses **General / Files / Performance** category pages.
Settings schema remains version 5.

General owns persistent RAW JSON confirmation, exact RAW file-size validation,
and native Difference Threshold/Gain defaults. Files owns optional default Open
and Export folders. Performance owns startup Decoded Source Memory, Difference Map
Cache, and preload settings.

Decoded Source Memory accounts native registered `ImageDocument.source` arrays
only and uses protected soft-budget LRU semantics. Source eviction and Difference
cache ownership remain independent. **Preload Next Folder Position** remains
exactly `+1`, one Folder Position deep, on a dedicated max-one worker; an exact
matching physically RUNNING preload may transfer logical authority to foreground
without duplicate decode.

P3-D adds no Settings key, Settings-owned profile library, or new RAW profile
version field.

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
ignores RAW Black/White levels, Display Gain, display transforms, preview values,
and demosaic. Cache metadata records domain/data range so reversed-pair reuse
cannot change threshold or metric semantics.

Threshold uses `code` in the native domain and `%FS` in the normalized domain;
mask comparison remains strict `>`. Persisted Settings Threshold remains the
native-domain code default under schema v5. Normalized threshold is session-local.

Difference owns its own independent presentation Gain. General Display Gain is
not applied to Difference numerical sources, Difference preview generation, or
Difference-cache identity.

## Display Gain contract

P3-B introduced the generic presentation primitive and P3-C generalized its viewer
activation:

```text
display = anchor + gain * (source - anchor)
```

The numerical core is not RAW-specific. It accepts a caller-supplied scalar
anchor, naturally supports `anchor=0`, uses float32 affine processing, and may be
applied to selected channel views. It never modifies native source data.

PixelScope exposes one application-session **Display Gain** control with:

```text
1× / 2× / 4× / 8× / 16×
```

The value is shared across supported Single/Multi View tiles and is not persisted
to application Settings, workspace state, or RAW profiles.

Document policy is:

- ordinary Gray/RGB use `anchor=0`;
- ordinary RGB split-channel views use `anchor=0` on their native source plane;
- RGBA applies gain to RGB only and preserves canonical 1× alpha exactly;
- RAW keeps the P3-B Black-derived anchor rules;
- Difference is excluded because it owns its own presentation Gain.

Gain 1× is a strict fast path: PixelScope reuses canonical
`ImageDocument.preview`, schedules no full-frame gain worker, and retains no
additional gained preview. Gain >1 derives only viewer-local preview from already
resident source on the existing shared numerical pool.

Display Gain is presentation-only. Pixel inspection, Statistics, Histogram, Line
Profile, Split Channel source arrays, Difference, generation, source residency,
and cache identity remain independent of it. `+` / `-` gain shortcuts are scoped
to the image-presentation subtree so Files retains native key behavior.

## RAW profile and decode contract

RAW profile resolution is conditional logic inside the unified image-opening
workflow; it is not a separate top-level file-opening mode.

A same-name JSON sidecar may pre-fill/resolve the profile. The General Settings
preference may skip repeated confirmation only when that sidecar is valid and the
configured exact/minimum file-size policy matches. When **Require Exact RAW File
Size** is disabled, RAW files may contain trailing bytes but may not be
undersized. When enabled, byte count must exactly match the profile requirement.

The RAW Profile dialog exposes **Load Profile...** and **Save Profile...**. JSON
remains the storage format and existing migration behavior is preserved. The
profile separates:

- storage format: unpacked, MIPI RAW10, RAW12, or RAW14;
- sample container for unpacked data: `uint8` or `uint16`;
- effective bit depth;
- byte order and LSB/MSB alignment where applicable;
- width, height, offset, stride, and grayscale/Bayer layout;
- Bayer pattern;
- `black_level` and `white_level` metadata, including R/Gr/Gb/B Black tuples for
  Bayer profiles.

The same RAW path may be resolved again with corrected profile settings while
retaining document identity/reload semantics.

The current product deliberately has no global RAW profile database, Settings-
owned profile collection, favorites, rename/duplicate/delete manager, profile
search UI, file-size-only or fuzzy suggestion, sensor-model inference, Bayer
pattern inference, or automatic Black/White estimation. Exact same-basename
sidecars remain supported because they are deterministic file-local evidence.

Decoded samples in `ImageDocument.source` are the native RAW authority. Pixel
inspection, Statistics, Histogram, Line Profile numerical data, Split Channels,
Difference, preload/reload identity, and source residency operate on those native
samples regardless of Display Gain.

## RAW display contract

RAW display is explicitly separate from analysis:

- at `Display Gain = 1×`, display range is native code
  `0..((1 << bit_depth) - 1)`;
- `black_level` is not subtracted from 1× display and `white_level` is not used as
  display maximum;
- gained RAW uses a Black-derived anchor, equivalently `B + G * (X - B)`;
- RAW Gray scalar Black is the scalar anchor;
- schema-valid GRAY four-value Black remains compatible and uses legacy
  `min(black_level)` as the global display anchor;
- Bayer tuple Black uses CFA-specific R/Gr/Gb/B anchors; scalar Bayer Black applies
  one anchor to all channels;
- split Bayer planes use the corresponding named-channel Black anchor;
- Bayer anchor processing does not create a full-size Black map;
- gain/range mapping uses float32 fused affine processing where possible and
  clipping occurs at final display conversion;
- `white_level` remains metadata only.

Gain changes regenerate only derived viewer presentation from resident source.
They do not reload/decode native RAW, change source residency ownership, bump
source generation, or change Difference cache identity.

Packed formats own their byte layout and fixed bit depth, so container,
endianness, and alignment controls do not apply. Bayer is analyzed as native
mosaic planes. Demosaic, white balance, CCM, tone mapping, and processed-RAW
analysis are outside the current product contract.

## Current P3 status and future scope

- P3-A Difference domain extension: complete, PR #22.
- P3-B RAW native/display semantics: complete, PR #24.
- P3-C Display Gain generalization: complete, PR #25, merge commit
  `7f6bef73e6712f6a14a4d401820a915196e25da2`.
- P3-D Unified Image Opening & RAW Profile Resolution: current slice.
- P3-E integrates and hardens the completed Difference/Display Gain/RAW/input
  semantics.

The earlier P3-D reusable Profile Library/suggestion plan is deferred. It should
return only if actual workflow evidence justifies persistent profile management or
a deterministic suggestion model.

Additional RAW clipping/highlight/shadow or Bayer observability remains optional.
Demosaic remains deferred unless a future owner-approved processed-preview scope
defines white balance, color, tone, metadata, and analysis boundaries coherently.
Later planned work includes persistent sessions and ROI management, remote IQA /
image evaluation, heatmaps, and validated standalone Windows distribution.