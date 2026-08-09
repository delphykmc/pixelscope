# PixelScope current state

Snapshot date: 2026-08-09
Current merged baseline / P3-A PR #22 merge commit:
`769588bf869847da844cfc0b77c008023d8b048b`

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

P2 — Runtime Foundation, Settings & Performance is complete. Its historical plan
is retained at
[`exec-plans/completed/p2-runtime-foundation-settings-performance.md`](exec-plans/completed/p2-runtime-foundation-settings-performance.md).

The active plan is
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md) for
**P3 — Image Semantics & RAW Processing**. P3-B RAW native/display semantics is
the next implementation slice.

## Current product baseline

### Workspace and navigation

- Folder-grouped Files tree with pending/loading/resident/error state.
- Ordered selection is the comparison model; Difference owns its selected pair.
- Fixed one-to-six-image Multi View geometry with primary-image behavior.
- PageUp/PageDown atomically moves one-to-six registered distinct folders by one
  Folder Position using the same pure planner that predicts preload targets.
- Left/Right moves through the selected-image set; Up/Down remains native Files
  tree navigation.
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
- RAW black/white levels, `DisplayTransform`, preview values, demosaic output, and
  implicit RGB→Gray conversion do not participate in P3-A normalization;
- normalized map generation and metrics use bounded chunks. P95/P99 use a fixed
  65,536-level histogram over `[0,1]`, giving deterministic quantile error no
  greater than `1/65535` full scale;
- `CachedDifferenceMap` stores `domain`, `data_range`, family/layout, and Bayer
  pattern metadata while retaining the existing order-independent generation key;
- compact Scope/Domain fields are primary UI status. Validation failures use short
  labels such as `Layout mismatch` while detailed reasons remain in tooltips.

Settings schema remains v5. Persisted `difference_threshold` is the native code
threshold default; normalized threshold starts at `1.00 %FS` and is session-local.

### RAW

Current RAW support includes:

- unpacked uint8/uint16 with effective depth, endian, stride, offset, and
  LSB/MSB alignment;
- MIPI RAW10/12/14;
- JSON profile load/save/migration and same-path reload;
- exact-versus-minimum RAW file-size policy;
- native grayscale/Bayer analysis without demosaic;
- `black_level` and `white_level` RAW-profile metadata;
- deterministic Bayer/RAW fixtures and UHD characterization.

The next P3-B contract is intentionally narrower than a RAW-conversion pipeline:

- native decoded RAW stays authoritative and unchanged;
- at 1× display gain, RAW is viewed in its native code domain;
- display gain is anchored at black level using
  `black + gain * (native - black)`;
- black/white metadata do not silently change native analysis or P3-A Difference;
- white level remains available as saturation/display metadata and for possible
  future explicit processing.

Not yet implemented:

- the revised black-anchored RAW display-gain contract;
- RAW visualization/inspection improvements planned for P3-C;
- reusable profile-management workflow;
- profile suggestion.

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
2. **P3-B — RAW Native & Display Semantics**
   - native RAW authority;
   - black-anchored display gain;
   - retain black/white metadata without redefining native analysis.
3. **P3-C — RAW Visualization & Inspection Improvements**
   - improve gain/exposure/clipping/Bayer observability where useful;
   - keep viewer-only changes out of analysis-domain semantics;
   - demosaic deferred unless separately approved with a coherent processing
     boundary.
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

P2 evidence leaves the following as optional future optimization, not current
roadmap commitments:

- preload concurrency one versus two;
- directional/bidirectional or deeper preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry.

They should be scheduled only when profiling or a reproducible user-visible
latency problem justifies changing the established P2 policy.
