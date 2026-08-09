# PixelScope roadmap

## Program direction

PixelScope is proceeding in staged, reviewable slices. Runtime/resource foundations
are complete; the current program is P3 — Image Semantics & RAW Processing.

The ordering is intentionally:

1. stabilize image and RAW semantics;
2. then build persistent workflow/session features on top of those semantics;
3. then add remote IQA, identity/access, and release engineering.

## P0 — Initial comparison foundation — Complete

- selection-driven Single/Multi View;
- Difference visualization;
- analysis panels;
- cache and layout foundations.

## P1 — Workspace/UI polish — Complete

- primary-image semantics;
- folder-pair navigation;
- Plots workspace behavior;
- fixed layout cleanup and compatibility removal.

## P2 — Runtime Foundation, Settings & Performance — Complete

Completed through PR #20.

- typed Settings and application identity;
- decoded-source residency budget;
- bounded next-position preload;
- runtime diagnostics;
- running-preload foreground promotion;
- integration/performance hardening.

## P3 — Image Semantics & RAW Processing — Active

### P3-0 — Program transition — Complete

Merged as PR #21.

### P3-A — Difference Gray / Mixed Bit-Depth Support — Complete

Merged as PR #22.

- Gray ↔ Gray Difference;
- RGB/RGBA ↔ RGB/RGBA and same-CFA Bayer compatibility;
- native equal-bit domain;
- independent full-scale normalized mixed-bit domain;
- explicit domain metadata and `%FS` threshold semantics;
- bounded float32 normalized computation.

### P3-B — RAW Native & Display Semantics — Implementation complete; final review follow-up pending validation/merge

P3-B establishes native RAW authority and the reusable Display Gain core without
changing analysis domains.

- decoded RAW source remains authoritative;
- Black/White remain profile metadata;
- 1× RAW display uses effective native full scale;
- RAW gain uses Black-anchored presentation;
- generic core is `display = anchor + gain * (source - anchor)`;
- gain/range work uses fused float32 affine processing where possible;
- 1× canonical-preview fast path is retained;
- hidden gain>1 viewer previews are released and regenerated on show;
- ordinary Gray/RGB/RGBA gain remains deferred to P3-C;
- `+` / `-` gain commands are scoped to the image-presentation subtree;
- Files-tree `+` / `-` native expand/collapse is preserved;
- latest pre-follow-up owner/local validation passed on
  `424144215b1df97c71a84ddca79a17bfccb1feef`; the final shortcut-focus review
  fix requires one more latest-head validation before merge.

### P3-C — RAW Visualization & Inspection Improvements + Display Gain Extension

After P3-B merges:

- reuse the generic Display Gain core for ordinary Gray/RGB/RGBA;
- use `anchor=0` for ordinary Gray/RGB;
- preserve RGBA alpha;
- use **Display Gain** / **Gain**, not Exposure;
- reuse the P3-B presentation-scoped `+` / `-` command policy;
- preserve Files-tree native expand/collapse and other sibling-widget key routing;
- preserve source/Statistics/Histogram/Line Profile/Difference domains;
- cover 1× identity, clipping, Gray/RGB/RGBA behavior, alpha preservation,
  analysis independence, command synchronization, and key-routing preservation;
- improve RAW clipping/Bayer observability where useful.

Demosaic is deferred unless separately approved together with a coherent
processed-preview contract covering Black/White normalization, white balance,
CCM, tone/gamma, and analysis interactions.

### P3-D — RAW Profile Management

- reusable profile storage/selection;
- deterministic profile suggestion;
- safe profile identity/versioning and edit workflow.

### P3-E — Integration & Hardening

- cross-analysis regression coverage;
- representative Gray/RGB/RGBA/Bayer/RAW characterization;
- preserve P2 runtime/resource boundaries;
- Windows validation and durable P3 closure documentation.

## P4 — Workflow & Session Productivity

- persistent comparison sessions;
- Recent Files/Folders;
- saved ROI workflow;
- arbitrary-angle line sampling;
- alpha overlay and broader local productivity/export features.

## P5 — Remote IQA Platform

- remote submission/results;
- versioned job API;
- GPU worker/evaluation;
- artifacts, heatmaps, and result comparison.

## P6 — Identity, Access & Remote Operations

- login/SSO;
- token/credential lifecycle;
- permissions and operational administration.

## P7 — Release Engineering & Distribution

- PyInstaller 5.7 `onedir` packaging;
- portable ZIP;
- Inno Setup installer;
- clean-PC smoke validation;
- signing, updater, and release process.

## Deferred optimization candidates

Performance changes remain evidence-driven rather than roadmap commitments.
Candidates include:

- preload concurrency/direction/depth changes;
- broader CPU/I/O aggressiveness controls;
- process-level memory profiling;
- coalescing/debounce/cancellable chunking for rapid large-image Display Gain
  changes if profiling demonstrates material latency or transient memory pressure;
- SIMD/native kernels only after profiling shows Python/NumPy paths are limiting.
