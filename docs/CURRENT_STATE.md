# PixelScope current state

Snapshot date: 2026-08-09
Current merged baseline / P3-B PR #24 merge commit:
`1817490a08c61da9087efe9c3c6afd8bd85838f0`

This document records the implementation baseline that new work must use.

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 merged as PR #13.
- P2-A1 merged as PR #14.
- P2-A2 merged as PR #15.
- P2-B merged as PR #16.
- P2-C merged as PR #17.
- P2-D merged as PR #18.
- P2-E merged as PR #19.
- P2-F merged as PR #20 at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3-0 roadmap transition merged as PR #21 at
  `5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.
- P3-A Difference Gray/mixed-bit support merged as PR #22 at
  `769588bf869847da844cfc0b77c008023d8b048b`.
- P3 roadmap replanning merged as PR #23 at
  `4c7d1bbbb4476134f76a204578098d35a03feca2`.
- P3-B RAW Native & Display Semantics merged as PR #24 at
  `1817490a08c61da9087efe9c3c6afd8bd85838f0`.

P2 — Runtime Foundation, Settings & Performance is complete. Its historical plan
is retained at
[`exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

The active plan is
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md) for
**P3 — Image Semantics & RAW Processing**. P3-B is complete as PR #24. P3-C
Display Gain Generalization & RAW Visualization is implemented on
`feature/p3-c-display-gain`; owner/local Windows validation is complete and
independent review/merge is pending. The merge-critical P3-C scope is Display
Gain generalization. Additional RAW clipping/highlight/shadow/Bayer observability
remains optional/deferred.

## Current product baseline

### Workspace and navigation

- Folder-grouped Files tree with pending/loading/resident/error state.
- Ordered selection is the comparison model; Difference owns its selected pair.
- Fixed one-to-six-image Multi View geometry with primary-image behavior.
- PageUp/PageDown atomically moves one-to-six registered distinct folders by one
  Folder Position using the same pure planner that predicts preload targets.
- Left/Right moves through the selected-image set; Up/Down remains native Files
  tree navigation.
- Files-tree `+` / `-` retains Qt-native expand/collapse behavior. Display Gain
  `+` / `-` is scoped to the image-presentation subtree and does not own those
  keys while focus is in Files.
- ROI uses Ctrl+drag and Esc; Line Profile uses Shift+drag and Shift+Esc.
- Plots floating geometry, selected tab, and workspace state persist separately
  from application settings.

### Analysis

- Full-image and Active ROI Statistics.
- Histogram Auto/256/1024/4096 bins and Count/Normalized/Log count modes.
- Statistics/Histogram identical numerical requests are idempotent across
  scheduled, running, and completed states when source identity/generation,
  layout/Bayer semantics, ROI, and histogram specification are unchanged.
- Line Profile supports absolute, normalized, and Difference-from-reference
  modes with primary→active→first-displayed reference priority.
- Difference supports Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA
  Bayer ↔ Bayer, with explicit native/normalized domains, byte-budgeted cache,
  threshold/gain display controls, mask, metrics, and reversed-pair reuse.
- Split Channels keeps atomic RGB/Bayer-to-GRAY replacement behavior.

### P3-A Difference semantics

P3-A is merged and establishes the production Difference contract:

- Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA Bayer ↔ Bayer are supported;
- cross-family, size-mismatch, CFA-mismatch, and unsupported layouts are rejected;
- Gray uses the complete 2-D source, RGB/RGBA compares RGB only, and Bayer keeps
  Mosaic/R/Gr/Gb/B semantics;
- equal effective bit depths retain compact native code-domain Difference with
  full scale `(1 << bit_depth) - 1`;
- mixed effective bit depths independently normalize each native source by its
  own effective full scale, produce canonical float32 absolute maps in `[0,1]`,
  and use `%FS` threshold semantics;
- RAW black/white levels, Display Gain, `DisplayTransform`, preview values,
  demosaic output, and implicit RGB→Gray conversion do not participate in P3-A
  normalization;
- normalized map generation and metrics use bounded chunks. P95/P99 use a fixed
  65,536-level histogram over `[0,1]`, giving deterministic quantile error no
  greater than `1/65535` full scale;
- `CachedDifferenceMap` stores `domain`, `data_range`, family/layout, and Bayer
  pattern metadata while retaining the existing order-independent generation key;
- compact Scope/Domain fields are primary UI status. Validation failures use short
  labels such as `Layout mismatch` while detailed reasons remain in tooltips.

Settings schema remains v5. Persisted `difference_threshold` is the native code
threshold default; normalized threshold starts at `1.00 %FS` and is session-local.

### RAW and Display Gain boundary

Current RAW support includes:

- unpacked uint8/uint16 with effective depth, endian, stride, offset, and
  LSB/MSB alignment;
- MIPI RAW10/12/14;
- JSON profile load/save/migration and same-path reload;
- exact-versus-minimum RAW file-size policy;
- native grayscale/Bayer analysis without demosaic;
- `black_level` and `white_level` RAW-profile metadata;
- deterministic Bayer/RAW fixtures and UHD characterization.

P3-B establishes the **generic anchor-based display-gain core**:

```text
display = anchor + gain * (source - anchor)
```

The generic core lives in the display-transform layer rather than encoding RAW
metadata rules itself. It supports scalar anchors, `anchor=0`, float32 fused
affine gain/range mapping, and operation on array/channel views.

P3-C generalizes the P3-B viewer presentation architecture to ordinary Gray/RGB/
RGBA while retaining one application-session value:

```text
1× / 2× / 4× / 8× / 16×
```

Document policy is:

- ordinary Gray/RGB use `anchor=0`;
- ordinary RGB split-channel views use `anchor=0` on their native source plane;
- RGBA applies gain to RGB only and copies alpha exactly from canonical 1×
  preview; alpha never participates in gain arithmetic;
- RAW Gray with scalar Black Level uses that scalar as the anchor;
- schema-compatible RAW Gray with four-value Black Level retains the legacy
  global-preview rule `min(black_level)`;
- RAW Bayer uses R/Gr/Gb/B CFA-parity-specific Black Levels where available;
- split Bayer planes use the corresponding named-channel anchor;
- `white_level` remains persisted metadata and is not a display-range authority;
- Difference is excluded from general Display Gain because Difference owns its
  own independent presentation Gain.

The Display Gain runtime contract is:

- decoded `ImageDocument.source` remains authoritative for pixel inspection,
  Statistics, Histogram, Line Profile numerical data, Split Channels, Difference,
  and source-residency accounting;
- RAW 1× display maps native code `0..((1 << bit_depth) - 1)` directly to the
  preview range. Black is not remapped to zero and White is not remapped to the
  display maximum;
- ordinary gain >1 is zero-anchored; RAW gain >1 remains
  `B + G * (X - B)`;
- gain arithmetic is float32 and gain/range normalization is fused into affine
  scale/offset processing where possible; no full-frame float64 gain path is used;
- Bayer channel Black handling operates on parity-plane views and never
  materializes a full-size Black Level map;
- RGBA runs full-frame gain arithmetic on the RGB source view only, then composes
  final uint8 RGBA using canonical 1× alpha rather than a four-channel float32
  gain buffer;
- viewer gain `1×` reuses canonical `ImageDocument.preview`, schedules no
  full-frame gain worker, and retains no additional gained preview;
- gain changes regenerate only derived viewer presentation from resident native
  source through the shared numerical worker pool. They do not reload/decode the
  source, alter source residency, bump source generation, or invalidate Difference;
- stale async Display Gain results are rejected against request/document/source/
  canonical-preview/generation/gain/visibility identity before they can overwrite
  newer presentation;
- hidden viewers release gain>1 viewer-local derived previews back to the
  canonical 1× document preview and regenerate the current gain when shown again;
- `+` / `-` gain commands are owned by the viewer-presentation subtree using
  `WidgetWithChildrenShortcut`. Files and sibling UI retain their native key
  handling; in particular, Files `+` / `-` continues to expand/collapse folders;
- generic session/UI ownership is `ui.display_gain`; RAW Black/CFA policy remains
  in the RAW/Bayer layers, with no permanent RAW-only UI compatibility wrapper.

The feature terminology is **Display Gain** or **Gain**, not Exposure. Source and
analysis data remain unchanged.

Not implemented in P3-C:

- demosaic, white balance, CCM/color conversion, tone mapping, or new gamma UI;
- processed RAW/document analysis;
- automatic Black estimation;
- reusable profile-management workflow or profile suggestion;
- gain persistence or Settings schema change;
- new Difference mode;
- preload/residency/worker-pool redesign;
- additional RAW clipping/highlight/shadow/Bayer visualization unless separately
  justified.

Demosaic is no longer a committed P3-C requirement. It is deferred until a
coherent processed-preview scope defines whether white balance, CCM, tone/gamma,
and related processing belong in PixelScope.

## P2 runtime/settings baseline

### Settings

Settings schema version 5 owns:

- RAW JSON confirmation;
- exact RAW file-size validation;
- optional default Open/Export folders;
- Difference Threshold/Gain defaults;
- Difference Map Cache MiB;
- Decoded Source Memory MiB;
- preload enablement.

P3-B/P3-C do not add a setting or schema migration. Display Gain is deliberately
session-local and returns to 1× on a new application session. The generic core
itself owns no persistence.

`ApplicationSettings` is the frozen typed persisted model. `SettingsRepository`
owns defaults, migration, validation, save/reset, corrupt-state recovery, and
future-schema compatibility; `QSettingsAdapter` owns raw application-setting
keys. Workspace QSettings remain a separate owner.

Difference Map Cache defaults to 128 MiB. Decoded Source Memory defaults to
256 MiB. The Settings UI enforces their product ranges and, when physical RAM is
known, a conservative combined limit of 50% of installed RAM.

### Source residency and Difference cache

- `ResidencyManager` accounts exact native `ImageDocument.source.nbytes`.
- Residency uses deterministic protected LRU soft-budget semantics.
- Visible/selected/analysis/Difference/foreground-authority sources are protected
  while required; unprotected sources may be evicted and reload through the
  existing tokenized worker path.
- Source eviction and Difference-cache ownership are independent.
- Difference cache remains a persistence-free byte-budgeted LRU; each entry
  records its native/normalized data-domain metadata independently of source
  residency.
- Viewer-local Display Gain previews remain derived presentation and are outside
  decoded-source residency and Difference-cache ownership.

### Preload and foreground reuse

- Normal image-load pool max: 2.
- Preload pool max: 1.
- Shared numerical pool max: 4.
- Preload remains `plan(+1)` only and exactly one Folder Position deep.
- Speculative preload starts only after foreground loading is idle.
- An exact matching RUNNING preload may transfer logical authority to foreground
  while the same physical worker/decode continues in the preload pool.
- Promotion is not thread migration and does not change pool limits.
- Cancellation remains advisory. Document/token/generation/request identity is
  the correctness authority for stale-result rejection.

### Diagnostics

- `RuntimeDiagnosticsSnapshot` is frozen, deterministic, bounded, sanitized, and
  observation-only.
- Source/Difference/worker/preload/stale/failure state can be inspected without
  starting/cancelling work or touching either LRU.
- Promotion is visible through a cumulative promotion counter.
- The only end-user diagnostics surface is **Help > Copy Diagnostics**; there is
  no live monitor, diagnostics dialog, refresh loop, or file export.

## P2 closure characterization

P2-F removed hardware-dependent elapsed-time assertions as merge gates and kept
wall-clock timing as observational output only. Deterministic representative
coverage includes FHD RGB uint8, FHD grayscale uint16, UHD Bayer uint16 RAW, and
existing real 4K RGB/RGGB10 fixtures.

Owner/local Windows validation covered navigation, preload/promotion, RAW/Bayer,
resource pressure, Difference, Settings restart semantics, diagnostics, and
Statistics/Histogram/Line Profile/Split Channels. Independent review found no
remaining production/test blocker before PR #20 merged.

Windows CI remains deferred until PySide6/pytest-qt/offscreen behavior and runner
cost are demonstrated reliably. Packaging/installer CI remains P7.

## Revised forward roadmap

The active P3 sequence is:

1. **P3-A — Difference Gray / Mixed Bit-Depth Support — Complete**
2. **P3-B — RAW Native & Display Semantics — Complete — PR #24**
   - merge commit `1817490a08c61da9087efe9c3c6afd8bd85838f0`;
   - native RAW authority;
   - generic anchor-based display-gain core;
   - effective-full-scale RAW display and Black-anchored RAW gain;
   - presentation-scoped `+` / `-` command policy preserving Files-tree keys;
   - retain Black/White metadata without redefining native analysis.
3. **P3-C — RAW Visualization & Inspection Improvements + Display Gain Extension — Implemented; owner/local validation complete; independent review/merge pending**
   - generalize one Display Gain UI/session/worker lifecycle to ordinary
     Gray/RGB/RGBA and RAW;
   - ordinary Gray/RGB anchor is zero; RGBA alpha is canonical 1× alpha;
   - ordinary split RGB gains its native plane; RAW split Bayer retains Black
     anchor semantics;
   - Difference is excluded from general Display Gain;
   - 1× canonical-preview no-work fast path and gain>1 async viewer-local lifecycle;
   - preserve source/Statistics/Histogram/Line Profile/Difference/residency domains;
   - reuse the presentation-scoped `+` / `-` policy; Files-tree expand/collapse
     remains native;
   - use Display Gain/Gain terminology, not Exposure;
   - additional RAW clipping/Bayer observability remains optional/deferred;
   - demosaic remains deferred unless separately approved with a coherent
     processing boundary.
4. **P3-D — RAW Profile Management**
   - reusable profiles and deterministic suggestion.
5. **P3-E — Integration & Hardening**.

Then:

- **P4 — Workflow & Session Productivity**;
- **P5 — Remote IQA Platform**;
- **P6 — Identity, Access & Remote Operations**;
- **P7 — Release Engineering & Distribution**.

P3/P4 remain intentionally reordered from the previous roadmap. Persistent
workflow state should be built after Difference/RAW analysis semantics are stable.

## Deferred optimization candidates

P2/P3 evidence leaves the following as optional future optimization, not current
roadmap commitments:

- preload concurrency one versus two;
- directional/bidirectional or deeper preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry;
- coalescing/debounce/cancellable chunking for rapid large-image Display Gain
  changes if profiling demonstrates visible latency or transient memory-bandwidth
  pressure.

Display-gain affine fusion is no longer in this deferred list: the generic P3-B
core fuses gain and display-range normalization while retaining float32 and
bounded ownership. Further SIMD/native optimization still requires profiling.
