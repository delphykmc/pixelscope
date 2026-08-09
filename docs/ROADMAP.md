# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Ordered selection, registered one-to-six-folder navigation, synchronized
  cursor/range/ROI/line state, and fixed one-to-six-image layouts.
- Statistics, Histogram, Line Profile, Difference, Split Channels, structured
  status, and persisted workspace/Plots state.
- RAW10/12/14 plus unpacked uint8/uint16 decoding with deterministic fixtures.
- P1-D/P1-E/P1-F workspace-polish program completed as PR #10–#12.
- Historical P1 plan:
  `docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`.

### P2 — Runtime Foundation, Settings & Performance

P2 is complete.

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

- P2-0 merged as PR #13.
- P2-A1 identity/resources merged as PR #14.
- P2-A2 typed settings/runtime integration merged as PR #15.
- P2-B byte-budgeted decoded-source residency merged as PR #16.
- P2-C bounded next-position preload merged as PR #17.
- P2-D deterministic runtime diagnostics merged as PR #18.
- P2-E RUNNING preload foreground reuse merged as PR #19.
- P2-F performance characterization/hardening merged as PR #20 at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.

P2 closes with settings schema v5, independent source/Difference memory budgets,
protected soft-budget source residency, `+1` one-position max-one preload,
RUNNING preload authority promotion, deterministic sanitized diagnostics, and
hardware-independent correctness/resource/lifecycle merge gates.

Historical P2 plan:
`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`.

## Revised forward sequence

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order is revised so image-analysis semantics stabilize before persistent sessions
and workflow state are built around them.

`P3 Image Semantics & RAW Processing`
→ `P4 Workflow & Session Productivity`
→ `P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

## P3 — Image Semantics & RAW Processing

P3-0 is complete as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`; implementation slices start from
the latest merged P3 prerequisite. P3 roadmap replanning merged as PR #23 at
`4c7d1bbbb4476134f76a204578098d35a03feca2`.

### P3-0 — Program transition — Complete

- Merged as PR #21 at `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.
- Archived P2 completion state, established the revised P3/P4 order, and created
  the active P3 execution plan.
- Documentation only.

### P3-A — Difference Gray / Mixed Bit-Depth Support — Complete

P3-A merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

The completed contract is:

- Gray ↔ Gray;
- RGB/RGBA ↔ RGB/RGBA;
- Bayer ↔ Bayer only with the same CFA pattern;
- reject cross-family, size-mismatch, and CFA-mismatch cases;
- no implicit RGB→Gray/luma conversion;
- same effective bit depth uses native code-domain Difference;
- different effective bit depths normalize each source by its own effective
  full-scale code value to `[0,1]` and use `%FS` threshold semantics;
- RAW Black/White metadata and display transforms do not define P3-A Difference
  normalization.

P3-A also delivers explicit Gray channel support, bounded float32 mixed-bit
Difference/metrics, cache domain metadata, compact Scope/Domain UI, and short
validation reasons with detailed tooltips.

### P3-B — RAW Native & Display Semantics — Complete

P3-B merged as PR #24 at
`1817490a08c61da9087efe9c3c6afd8bd85838f0`.

Delivered contract:

- Native decoded RAW remains the authoritative source and is not modified by
  Black/White metadata or viewer controls.
- Existing `black_level` and `white_level` RAW-profile metadata remain schema- and
  JSON-compatible; Settings stays at schema v5.
- At 1× display gain, RAW maps native code `0..((1 << bit_depth) - 1)` to the
  preview range. Black is not subtracted and White is not promoted to full scale.
- P3-B introduces a **generic anchor-based display-gain core**:
  `display = anchor + gain * (source - anchor)`.
- The generic core is presentation-only and is not RAW-metadata-aware. RAW adapters
  supply the anchor policy: scalar Black for RAW Gray, channel-specific R/Gr/Gb/B
  Black for Bayer where available, and the legacy `min(tuple)` anchor for
  schema-compatible GRAY tuple profiles.
- The core naturally supports `anchor=0` and operation on channel views so
  ordinary Gray/RGB/RGBA presentation can reuse it without a second gain engine.
- Gain/range mapping uses float32 fused affine processing where possible. It does
  not create a full-size Bayer Black map or promote full-frame gain math to
  float64.
- `white_level` remains metadata only for RAW display; effective full scale is the
  RAW display-range authority.
- Pixel inspection, Statistics, Histogram, Line Profile source data, Split
  Channels, source residency, and P3-A Difference remain native-domain operations.
- P3-B established session-local 1×/2×/4×/8×/16× gain, a canonical 1× fast path,
  gain>1 viewer-local async presentation, stale-result rejection, and hidden-view
  derived-preview release.
- The `+` / `-` gain commands are scoped to the image-presentation subtree with
  `WidgetWithChildrenShortcut`. Files keeps Qt-native `+` / `-` folder
  expand/collapse.

P3-B intentionally adds no demosaic, white balance, CCM, tone mapping, processed
RAW document/analysis, persistence, Settings migration, or resource-policy
redesign.

### P3-C — RAW Visualization & Inspection Improvements + Display Gain Extension — Complete

P3-C merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

Delivered Display Gain scope:

- one application-session **Display Gain** state/control provides
  `1× / 2× / 4× / 8× / 16×` across supported viewer presentations;
- ordinary Gray and RGB use `anchor=0`;
- ordinary RGB split-channel views gain their native source plane with `anchor=0`
  while retaining colored presentation;
- RGBA applies gain to RGB only and preserves canonical 1× alpha exactly, without
  running gain arithmetic over a four-channel float32 working buffer;
- RAW keeps the P3-B 1× effective-full-scale and gain>1
  `B + G * (X - B)` semantics, including existing Gray/Bayer Black-anchor policy;
- Difference is excluded from general Display Gain and retains independent
  Difference-panel Gain/cache semantics;
- the user-facing term is **Display Gain** or **Gain**, not **Exposure**;
- 1× reuses canonical `ImageDocument.preview`, schedules no gain worker, and
  retains no extra derived preview;
- gain>1 uses resident source and the shared numerical worker pool with explicit
  stale-result acceptance checks;
- hidden/replaced viewers release unnecessary gain>1 derived buffers and
  regenerate current session gain when shown again;
- native Gray/RGB/RGBA/RAW source arrays, Statistics, Histogram, Line Profile,
  Difference, residency, and cache semantics remain independent of Display Gain;
- `+` / `-` stepping remains viewer-scoped and Files-tree native expand/collapse
  remains intact;
- Settings schema remains v5 and Display Gain is not persisted.

Owner/local Windows validation was completed on the implementation before merge.
Additional RAW clipping/highlight/shadow/Bayer observability remains optional and
deferred rather than part of the completed P3-C contract.

Demosaic remains deferred. A future demosaic feature must first define the
processed-preview boundary and whether white balance, color correction,
tone/gamma, and related metadata belong in the same feature.

### P3-D — Unified Image Opening & RAW Profile Resolution — In progress

P3-D replaces the earlier speculative Profile Library/suggestion scope with the
workflow actually needed by the product.

Authoritative contract:

- one top-level **Open Images...** command handles `.png`, `.bmp`, `.jpg`, `.jpeg`,
  and `.raw`; **Open Folder...** remains the folder entry point;
- there is no separate **Open RAW with Profile...** command or Empty Workspace
  RAW-open button/signal;
- `ImageInput`/path discovery is the common input contract for file picker,
  folder discovery, drag/drop, Folder Position registration/navigation, preload,
  reload, and sidecar reload ownership;
- ordinary PNG/BMP/JPEG bypass RAW profile UI and use the ordinary decoder;
- RAW with an exact same-basename `.json` sidecar retains current validation,
  confirmation suppression, and exact/minimum file-size policy;
- RAW without a sidecar opens the editable RAW Profile dialog;
- invalid sidecars warn and fall back to editable profile entry; cancel does not
  register the RAW document;
- multi-file RAW open resolves each RAW independently and does not introduce last-
  profile reuse or apply-to-all behavior;
- profile UI uses **Load Profile...** / **Save Profile...** terminology while JSON
  remains the compatible storage format;
- existing `RawProfile` schema/migration, packed/unpacked validation, Bayer
  pattern, Black/White metadata, and Settings schema v5 remain unchanged.

P3-D explicitly does **not** add a global profile library, favorites/CRUD manager,
profile search, file-size-only/fuzzy suggestion, sensor/Bayer inference, automatic
Black/White estimation, or a new profile version field. Same-basename sidecars are
kept because they are deterministic evidence. A broader reusable-profile workflow
is deferred until real workflow evidence justifies it.

### P3-E — Integration & Hardening

- Cross-check native/normalized Difference with RAW native/display ownership and
  unified input/profile resolution.
- Characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Complete automated/Windows validation and durable P3 documentation.

P3 excludes persistent sessions, remote/authentication work, release engineering,
broad MainWindow/shortcut rewrites, speculative preload-policy expansion, native
optimization without profiling evidence, and demosaic/white-balance/color/tone
processing unless separately approved by the owner.

## P4 — Workflow & Session Productivity

This is the former P3 scope, intentionally moved after image/RAW semantics.

- Persistent comparison sessions.
- Recent Files/Folders.
- Saved ROI manager.
- Arbitrary-angle line sampling.
- Alpha overlay.
- Additional productivity and export workflows.

## P5 — Remote IQA Platform

- Remote submission and result workflow.
- Server/job API.
- GPU worker.
- Artifact, heatmap, and result comparison.

## P6 — Identity, Access & Remote Operations

- Login and SSO.
- Token/credential lifecycle.
- Permission and access policy.
- Operational administration.

## P7 — Release Engineering & Distribution

- Exactly PyInstaller 5.7 `onedir`.
- Portable ZIP.
- Inno Setup.
- Clean-PC smoke testing.
- Signing.
- Update strategy.
- Repeatable release process.

## Deferred optimization outside the phase sequence

P2/P3 characterization leaves several evidence-driven optimization candidates
that do not currently justify reopening the runtime foundation:

- preload concurrency one versus two;
- directional/bidirectional or deeper preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry;
- coalescing/debounce/cancellable chunking for rapid large-image Display Gain
  stepping if profiling demonstrates material latency or transient memory pressure;
- native/SIMD gain optimization beyond the current float32 fused affine path.

These should be scheduled only when later profiling or user-visible latency gives
a concrete reason to change the established runtime policy.