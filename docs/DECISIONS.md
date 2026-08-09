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
- **Open Images...** is the one top-level file-open command for PNG/BMP/JPEG/RAW;
  RAW-specific profile resolution is conditional logic inside the common input
  pipeline rather than a second user-facing open mode.
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

P3-B merged as PR #24 at
`1817490a08c61da9087efe9c3c6afd8bd85838f0` and introduced RAW viewer gain without
redefining native analysis.

### Native RAW authority

- `ImageDocument.source` remains the decoded native authority.
- Pixel inspection, Statistics, Histogram, Line Profile, Split Channels,
  Difference, and source residency consume native source rather than gained
  preview pixels.
- Gain changes do not reload/decode source, bump generation, alter source
  residency, or change Difference-cache identity.
- `white_level` remains persisted profile metadata and is not the 1× or gained
  display maximum.

### Generic display-gain core

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
- Generic affine application can target an array/channel view.
- Clipping is deferred to final display conversion.
- Source arrays are not modified.

### RAW anchor policy

- RAW 1× display maps effective native full scale
  `0..((1 << bit_depth) - 1)` to the preview range.
- Black is not subtracted at 1× and White is not promoted to display maximum.
- RAW Gray scalar `black_level` is the gain anchor.
- A schema-valid GRAY profile with four Black values remains compatible and uses
  the legacy global-preview anchor `min(black_level)` while preserving the tuple.
- Bayer four-value Black uses R/Gr/Gb/B channel-specific anchors by CFA parity.
- Scalar Bayer Black applies one anchor to all channels.
- Split Bayer planes use their named channel anchor.
- Bayer processing operates on parity-plane views and never materializes a
  full-size Black Level map.

### P3-B UI/runtime policy

- session-local gain choices are 1×/2×/4×/8×/16×;
- gain is not persisted to `RawProfile`, workspace QSettings, or
  `ApplicationSettings`; schema remains v5;
- gain 1× uses canonical `ImageDocument.preview` and schedules no gained-preview
  worker;
- gain >1 derives a viewer-local preview from resident source on the shared
  numerical worker pool;
- result acceptance checks task/request/document/source/generation/gain/visibility
  identity;
- hidden viewers release gain>1 derived buffers and regenerate current gain when
  shown;
- `+` / `-` Display Gain command ownership is the image-presentation subtree,
  preserving Files-tree native expand/collapse.

## Accepted P3-C Display Gain generalization decisions

P3-C merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

- The user-facing term is **Display Gain** or **Gain**, never **Exposure**.
- One QApplication-session `DisplayGainState` serves supported ordinary and RAW
  presentations using 1×/2×/4×/8×/16×.
- Ordinary Gray/RGB use the P3-B core with `anchor=0`.
- Ordinary RGB split-channel views gain their native 2-D source plane with
  `anchor=0` while retaining colored presentation.
- RGBA applies gain only to RGB; gain>1 alpha equals canonical 1× alpha exactly.
- RGBA gain arithmetic targets the RGB source view rather than a four-channel
  float32 gain buffer.
- RAW P3-B semantics remain unchanged.
- Difference is excluded from general Display Gain.
- Gain 1× is a no-work canonical-preview reuse path; gain>1 uses resident source
  and the existing shared numerical worker pool.
- Stale results are rejected by explicit request/document/source/preview/
  generation/gain/visibility identity.
- Hidden/replaced viewers release unnecessary gain>1 derived buffers.
- Display Gain never mutates native source/generation, source residency, analysis,
  or Difference-cache identity.
- No new worker pool, resource setting, persistence, or schema migration was
  introduced.

## Accepted P3-D unified opening decisions

P3-D's authoritative product goal is **Unified Image Opening & RAW Profile
Resolution**. The earlier reusable Profile Library/suggestion concept is deferred.

### One image-opening surface

- The File menu exposes **Open Images...** and **Open Folder...** only.
- `Ctrl+O` remains Open Images; `Ctrl+Shift+O` remains Open Folder.
- Empty Workspace exposes the same two actions and no RAW-only signal/button.
- Open Images accepts exactly `.png`, `.bmp`, `.jpg`, `.jpeg`, and `.raw` and uses
  `Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)`.
- A wildcard RAW filter is prohibited because unsupported extensions must not be
  interpreted as RAW.

### One input-resolution contract

- `io.path_discovery` owns the supported-extension contract.
- `ImageInput` remains the authoritative path plus optional sidecar identity.
- Open Images, Open Folder, drag/drop, folder discovery/registration, Folder
  Position workflows, preload, reload, and sidecar reload must converge on the
  same registration/profile-resolution semantics rather than duplicate UI-specific
  RAW handling.
- `.json` is sidecar metadata only and never an image-tree entry.
- Ordinary image inputs never instantiate `RawOpenDialog`.

### RAW profile-resolution order

1. If an exact same-basename sidecar exists, parse and validate that profile.
2. Preserve the current confirmation-suppression preference and exact/minimum
   source-size policy; suppression is allowed only for a valid compatible sidecar.
3. If no sidecar exists, open the editable RAW Profile dialog.
4. If the sidecar is invalid, warn and open editable fallback instead of silently
   applying it.
5. If profile entry is cancelled, do not register the RAW document.
6. When multiple RAW files are selected, resolve each independently.

Existing same-path reload, RawProfile identity, preload identity, packed/unpacked
validation, Bayer pattern, Black/White metadata, and legacy JSON storage-field
migration remain unchanged.

### Profile UI and persistence boundary

- User-facing buttons are **Load Profile...** and **Save Profile...**; JSON is a
  storage implementation detail and remains the compatible file format.
- Settings schema remains v5.
- RawProfile gains no artificial version field solely for this slice.
- No global profile database/library, Settings-owned profile collection,
  favorites, rename/duplicate/delete manager, search UI, size-only/fuzzy profile
  selection, sensor inference, Bayer-pattern inference, or Black/White estimation
  is introduced.
- Same-basename sidecars remain because they are deterministic file-local evidence.
  A broader profile-management/suggestion feature requires future workflow
  evidence before it can become roadmap scope.

### Scope preservation

P3-D does not redesign Difference, Display Gain, residency/preload, worker pools,
session persistence, Recent Files/Folders, demosaic, white balance, CCM, tone
mapping, or packaging. Native source remains authoritative and all P3-A/B/C
analysis/display boundaries are unchanged by image-opening UX.

## Current resource policy

- Difference Map Cache remains byte-budgeted and persistence-free with default
  128 MiB.
- Decoded-source residency remains a protected soft-budget manager with default
  256 MiB.
- Normal load pool max remains two; preload pool max remains one; shared numerical
  pool max remains four.
- Display Gain derived previews are viewer-local presentation buffers and are not
  added to decoded-source residency or Difference cache ownership.
- Unified input resolution introduces no cache, persistence, or resource-policy
  owner.

## Validation and merge state

P3-A/B/C are merged. P3-C is complete as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

P3-D test code is added for unified menu/filter/Empty Workspace behavior,
ordinary-image RAW-dialog bypass, valid/no/invalid sidecars, cancel safety,
multi-RAW identity, exact/minimum-size policy, mixed folder/drop discovery, and
profile terminology. Existing regression suites remain authoritative for folder
navigation/preload/reload, residency, Difference, Display Gain,
Statistics/Histogram/Line Profile, and Split Channels.

The Chat implementation agent has not run the repository validation commands.
Owner/local Windows validation is required before P3-D merge.