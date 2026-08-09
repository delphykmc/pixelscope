# PixelScope product specification

PixelScope is a Windows desktop engineering tool for local image comparison,
analysis, and RAW inspection. The product favors explicit numerical semantics,
native-sample authority, predictable resource ownership, and reproducible behavior
over camera-like rendering or hidden conversion.

## Core comparison workflow

- Register files/folders and keep them grouped by folder.
- Select one to six images for Single/Multi View comparison.
- Use fixed Multi View layouts with an explicit primary image where applicable.
- Navigate selected folder groups atomically by Folder Position.
- Inspect pixels, Statistics, Histogram, Line Profile, Split Channels, and
  Difference without silently changing the source domain.

## Difference contract

Difference supports compatible Gray, RGB/RGBA, and same-CFA Bayer pairs.

- Equal effective bit depth uses native code-domain absolute Difference.
- Mixed effective bit depth independently normalizes each source by its own
  effective full scale and uses a normalized `[0,1]` Difference domain.
- RGB/RGBA ignores alpha; Bayer keeps Mosaic/R/Gr/Gb/B semantics.
- Cross-family, dimension, CFA, and unsupported-layout mismatches are rejected.
- RAW Black/White metadata, viewer display transforms, previews, and demosaic do
  not participate in Difference domain selection.

## RAW native/display contract

Decoded RAW source values remain authoritative. Black Level and White Level are
profile metadata, not implicit instructions to redefine native analysis.

At RAW Gain 1×, the viewer maps effective native full scale
`0..((1 << bit_depth) - 1)` to the preview. Black is not remapped to zero and
White is not promoted to the display maximum.

For gained RAW presentation, PixelScope uses the generic anchor model:

```text
display = anchor + gain * (source - anchor)
```

- RAW Gray uses its Black Level as the anchor.
- Schema-compatible four-value Gray Black Level keeps the legacy global anchor
  `min(black_level)`.
- Bayer uses R/Gr/Gb/B Black anchors at the matching CFA parity positions.
- White Level remains metadata only under the current P3-B display contract.
- Gain is presentation-only; source values, Statistics, Histogram, Line Profile,
  Split Channels, Difference, generation, and source residency remain unchanged.

P3-B exposes one session-local RAW Gain control with 1×/2×/4×/8×/16×. Gain 1×
reuses the canonical preview; higher gains derive viewer-local previews from
resident native source and reject stale asynchronous results.

Display Gain keyboard commands are scoped to the image-presentation surface.
While the viewer has focus, `+` / `-` steps the same discrete gain control and
clamps at its endpoints. The Files tree retains native Qt `+` / `-` folder
expand/collapse behavior instead of being overridden by the gain command.

## Generic Display Gain direction

The numerical Display Gain core is intentionally reusable beyond RAW. P3-C is
planned to activate it for ordinary Gray/RGB/RGBA viewer presentation:

- Gray/RGB use `anchor=0`.
- RGBA applies gain to RGB and preserves alpha exactly.
- The feature name is Display Gain/Gain, not Exposure.
- 1× remains an identity/no-work fast path where possible.
- Source and analysis domains remain unchanged.
- P3-C reuses the P3-B presentation-scoped `+` / `-` command policy and must
  preserve Files-tree key routing.

Demosaic is not currently required. It remains deferred until a coherent processed
preview contract defines Black/White normalization, white balance, CCM,
tone/gamma, and analysis interactions together.

## Resource/runtime contract

- Decoded Source Memory accounts native source arrays only.
- Difference Map Cache is independently byte-budgeted.
- Previews, Qt textures, display-gain derived buffers, and transient worker arrays
  are outside decoded-source accounting.
- Numerical/I/O work that can be expensive stays off the UI thread.
- Cancellation is advisory; request/document/generation identity rejects stale
  results.
- Rapid large-RAW gain stepping may temporarily leave superseded full-frame work
  running. Coalescing/debounce/cancellable chunking is profiling-driven future
  optimization, not a current correctness requirement.

## Persistence

RAW/Display Gain is session-local in P3-B and does not add a Settings schema key.
Application Settings schema remains version 5. Workspace persistence remains
separate from typed application preferences.

## Platform constraints

- CPython 3.10 x64
- PySide6 6.4.2
- pyqtgraph 0.13.3
- future packaging with exactly PyInstaller 5.7 `onedir`
- Inno Setup planned for installer distribution
