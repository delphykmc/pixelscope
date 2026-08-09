# Engineering decisions

## Platform and implementation constraints

- CPython 3.10 x64 is fixed.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image and plot
  primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; 6.x is prohibited. Inno Setup is
  the planned installer layer.
- NumPy/OpenCV implementations come first. Native C/C++ optimization requires
  profiling evidence and remains behind numerical/image interfaces.
- Expensive I/O and numerical work runs in bounded workers; widgets do not own
  decode, Difference, or full-frame display algorithms.
- Source pixels retain native dtype/channel meaning. Overflow-prone arithmetic
  promotes operands before subtraction/multiplication.
- Presentation transforms do not redefine source or analysis domains.

## Current product decisions

- Ordered selection is the comparison model; Difference may select any two current
  images.
- Multi View has one fixed layout policy. `_fixed_geometry()` is the sole geometry
  authority; P1-F removed arrangement compatibility state.
- Primary-image analysis reference priority is primary, active, then first
  displayed.
- Difference caches one absolute map per order-independent document-generation
  pair and derives views/metrics from it. The map explicitly records native or
  normalized domain metadata.
- RAW storage format, sample container, effective bit depth, endian, alignment,
  Black Level, and White Level remain separate concepts.
- Remote evaluation uses a versioned REST job API boundary.

## Accepted P2 program decisions

P2 — Runtime Foundation, Settings & Performance completed sequentially through
P2-F as PR #13–#20. The merged P2 baseline establishes these durable boundaries.

### Settings and identity

- QSettings is a persistence adapter, not the application settings domain model.
- Frozen `ApplicationSettings` is the typed persisted model;
  `SettingsRepository` owns defaults, validation, migration, save/reset, corrupt
  recovery, and future-schema compatibility; `QSettingsAdapter` owns raw keys.
- Settings schema version 5 owns RAW confirmation/exact-size policy, optional
  Open/Export folders, Difference Threshold/Gain defaults, Difference Map Cache
  MiB, Decoded Source Memory MiB, and preload enablement.
- Schema v4 migrates to v5 by preserving values and adding enabled preload. Older
  schemas and the legacy RAW-confirmation key remain supported. A future schema
  is never guessed or destructively rewritten.
- Settings UI uses General, Files, and Performance categories. Workspace geometry,
  splitter/dock state, current layout, Plots state, and last-directory state remain
  separate workspace persistence.
- Difference Map Cache defaults to 128 MiB. Decoded Source Memory defaults to
  256 MiB. When physical RAM is known, the Settings UI constrains the combined
  configured budgets to at most 50% of RAM; this is a configuration envelope,
  not a process-memory guarantee.
- Performance budgets and preload enablement are startup snapshots; edits persist
  for the next launch and do not mutate existing runtime owners.
- `Reset Settings` resets schema-owned application preferences only; workspace
  reset remains separate.
- Canonical source-run identity uses the package SVG/PNG/ICO triplet and stable
  Windows AppUserModelID `PixelScope.PixelScope`. Installer/signing/release-shell
  identity remains P7.

### Source residency

- Decoded Source Memory accounts exact native `ImageDocument.source.nbytes` only.
- `ResidencyManager` owns byte accounting, protected soft-budget LRU order,
  eviction planning, and bounded diagnostics; `MainWindow` owns document mutation.
- Visible, selected, active/analysis, Difference-pair, and foreground-authority
  sources are protected while required.
- One required source may exceed the entire soft budget while protected.
- Preview arrays, Qt textures, Difference maps, derived presentation buffers,
  transient worker arrays, Python/Qt overhead, and process RSS are not source
  residency.
- Source eviction and Difference-cache ownership are independent. Evicting source
  does not invalidate a valid generation-keyed Difference map.

### Navigation, preload, and promotion

- PageUp/PageDown owns previous/next Folder Position; Up/Down remains Files-tree
  navigation and Left/Right remains previous/next selected image.
- One pure folder-navigation planner is authoritative for actual movement and
  preload prediction.
- Preload policy is `+1` only, exactly one Folder Position deep, enabled by
  default, and concurrency one in a dedicated pool. Normal image-load pool max is
  two.
- Completed speculative preload enters ordinary source residency with no
  speculative protection or separate memory budget.
- Cancellation is advisory; token/generation/request identity is the authority
  for stale-result rejection.
- P2-E promotion applies only to an exact matching physically RUNNING preload.
  Promotion is a logical authority transition, not thread migration; the worker
  stays in the preload pool.
- Promotion requires exact document/generation/path/RAW-profile/exact-size/token
  identity, running/not-cancelled state, non-resident source, and no duplicate
  normal worker.
- Promoted success/failure delegates exactly once to normal foreground behavior.
  Promotion does not promote an entire group or change pool limits.

### Diagnostics and P2 closure

- Runtime diagnostics are deterministic, bounded, sanitized, and observation-only.
- The sole user surface is **Help > Copy Diagnostics**. There is no live monitor,
  timer, modal diagnostics viewer, refresh loop, or diagnostics file export.
- Diagnostics may not touch LRUs, load/preload, calculate Difference, mutate
  selection, or scan files.
- Recent failures are bounded and sanitized for paths, credential-like values,
  bearer data, URL detail, traceback context, and excess length.
- P2-F merge gates are deterministic correctness/resource/lifecycle properties.
  Wall-clock timing is observational only.
- Windows CI remains deferred until Qt/offscreen reliability and runner cost are
  demonstrated; owner/local Windows validation is the current closure authority.

## Accepted P3-A Difference decisions

P3-A merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

- Supported Difference families are Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and
  same-CFA Bayer ↔ Bayer. RGB/RGBA ignores alpha.
- Cross-family, size-mismatch, CFA-mismatch, and unsupported layouts are rejected.
  No implicit RGB→Gray/luma conversion is permitted.
- Family compatibility is decided before effective bit depth.
- Equal effective bit depth uses native code-domain Difference and compact integer
  storage with data range `(1 << bit_depth) - 1`.
- Mixed effective depth independently normalizes each source by its own effective
  full scale, stores canonical float32 absolute maps in `[0,1]`, and uses `%FS`
  threshold semantics.
- Mixed-bit normalized work is bounded/chunked and avoids full-size float64
  normalized arrays. P95/P99 use a deterministic 65,536-level histogram.
- Difference cache entries explicitly store domain/data-range/family/layout/Bayer
  metadata while retaining order-independent generation-pair identity.
- RAW Black/White metadata, display transforms, viewer gain, preview pixels,
  demosaic output, and other presentation state never participate in P3-A domain
  selection or normalization.
- Normalized threshold is session-local; schema v5 is unchanged.

## Accepted P3-B RAW/display decisions

P3-B is implemented on `feature/p3-b-raw-native-display-semantics` and introduces
RAW viewer gain without redefining native analysis.

### Native RAW authority

- `ImageDocument.source` remains the decoded native authority.
- Pixel inspection, Statistics, Histogram, Line Profile, Split Channels,
  Difference, and source residency consume native source rather than gained
  preview pixels.
- Gain changes do not reload/decode source, bump generation, alter source
  residency, or change Difference-cache identity.
- `white_level` remains persisted profile metadata and is not the 1× or gained
  display maximum in P3-B.

### Generic display-gain core

P3-B intentionally does **not** make the numerical gain implementation RAW-only.
The common core model is:

```text
display = anchor + gain * (source - anchor)
```

- `core.display_transform` owns the generic anchor-based numerical primitive.
- RAW metadata interpretation remains outside the generic primitive.
- The core supports scalar anchors including `anchor=0`.
- Gain and display-range normalization are fused into float32 scale/offset where
  possible to reduce full-frame memory-bandwidth passes.
- Full-frame display-gain arithmetic does not promote to float64.
- Generic affine application can target an array/channel view; this is the
  architectural hook for future RGBA RGB-only gain with alpha preservation.
- Clipping is deferred to final display conversion.
- Source arrays are not modified.

This generalization prepares P3-C reuse but does **not** broaden the P3-B product
surface. P3-B activates gain only for RAW.

### RAW anchor policy

- RAW 1× display maps effective native full scale
  `0..((1 << bit_depth) - 1)` to the preview range.
- Black is not subtracted at 1× and White is not promoted to display maximum.
- RAW Gray scalar `black_level` is the gain anchor.
- A schema-valid GRAY profile with four Black values remains compatible and uses
  the pre-P3-B global-preview anchor `min(black_level)` while preserving the
  stored tuple.
- Bayer four-value Black uses R/Gr/Gb/B channel-specific anchors by CFA parity for
  RGGB/GRBG/GBRG/BGGR.
- Scalar Bayer Black applies one anchor to all channels.
- Split Bayer planes use their named channel anchor.
- Bayer processing operates on parity-plane views and never materializes a
  full-size Black Level map.

### P3-B UI/runtime and lifetime policy

- The product surface is one session-local `RAW Gain` selector with
  1×/2×/4×/8×/16×.
- It is not persisted to `RawProfile`, workspace QSettings, or
  `ApplicationSettings`; schema remains v5.
- All RAW viewers consume one QApplication-session gain. Ordinary Gray/RGB/RGBA
  documents are not transformed by this control in P3-B.
- Gain 1× uses the canonical `ImageDocument.preview` fast path and schedules no
  gained-preview worker.
- Gain >1 derives a viewer-local preview from resident source on the shared
  numerical worker pool.
- Result acceptance checks task/request/document/source/generation/gain/visibility
  identity.
- Hidden viewers release gain>1 derived buffers back to canonical 1× presentation
  and regenerate current gain when shown.
- QApplication-global `RawDisplayState` may outlive toolbar controls. State/control
  connections therefore use QObject receiver lifetime rather than Python closures
  that can retain dead Qt wrappers.

### P3-B scope exclusions

P3-B adds no ordinary-image gain UI/runtime activation, demosaic, white balance,
CCM, tone-map feature, optical-Black estimation, processed RAW document/analysis,
new Difference mode, profile management/suggestion, persistence, Settings schema
bump, resource-policy redesign, packaging, or broad MainWindow/toolbar redesign.

## Accepted P3-C Display Gain extension decision

P3-C remains **RAW Visualization & Inspection Improvements** and now also owns the
ordinary-image activation of the P3-B generic display-gain core.

- Ordinary Gray and RGB viewer presentation uses the same core with `anchor=0`.
- RGBA uses the same RGB gain while preserving alpha exactly.
- User-facing terminology is **Display Gain** or **Gain**. Do not name the feature
  **Exposure**; it is an explicit digital display transform rather than a camera
  exposure model.
- Gain changes remain presentation-only. Gray/RGB/RGBA source arrays, generation,
  Statistics, Histogram, Line Profile, Difference, residency, and cache semantics
  remain unchanged.
- P3-C must retain a 1× identity/no-work fast path and deterministic final
  clipping.
- Required regression scope includes 1× identity, clipping, Gray, RGB, RGBA alpha
  preservation, Single/Multi consistency, and analysis independence.
- Large-image gain work remains off the UI thread where full-frame numerical work
  is required; stale result identity remains mandatory.
- Additional clipping/highlight/shadow and Bayer observability may be added where
  useful for engineering inspection, but viewer presentation does not create a
  processed-image analysis domain.
- Demosaic is deferred unless a separately approved coherent processed-preview
  boundary also defines White/Black normalization, white balance, CCM, tone/gamma,
  and analysis interactions.

## Current resource policy

- Difference Map Cache remains byte-budgeted and persistence-free with default
  128 MiB.
- Decoded-source residency remains a protected soft-budget manager with default
  256 MiB.
- Normal load pool max remains two; preload pool max remains one; shared numerical
  pool max remains four.
- Display-gain derived previews are viewer-local presentation buffers and are not
  added to decoded-source residency or Difference cache ownership.
- The generic gain core does not become a cache, persistence, or resource-policy
  owner.

## Validation and merge state

Owner/local Windows quality validation passed after the independent-review,
GRAY-tuple compatibility, hidden-preview lifecycle, and Qt control-lifetime fixes
at `1a8a904895566f27e17d175b43a94997e43401e4`.

The later owner-approved generic display-gain core refactor changes production
core code, tests, architecture, and P3 planning docs. Therefore final P3-B
latest-head validation is required again before merge. The Chat implementation
agent must not claim that latest-head gate passed until owner/local output is
observed.
