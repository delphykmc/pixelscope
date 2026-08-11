# Roadmap

## Delivered baseline

PixelScope has completed the P0/P1 product foundation, P2 runtime/settings/performance
program, and P3 image-semantics/RAW-input program.

Key completed milestones:

- P1-D/P1-E/P1-F workspace polish: PR #10–#12.
- P2 runtime/settings/performance: PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3 image semantics and RAW input: PR #21–#27; P3-E merged at
  `835634a58609601605fd0fc18a3028b64225f535`.
- P4-0 program setup: PR #28 at
  `e30c49d6759715228a820d673ad8939ea9a3afe8`.
- P4-A Review Selection & Curation: PR #29 at
  `3486146494076e9b513843b90ec44e504043729e`.

The inherited runtime hierarchy remains:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
Presented
    ↓
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

## Forward sequence

`P4 Workflow Productivity`
→ `P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

## P4 — Workflow Productivity — Active

Recommended sequence:

`P4-0 → P4-A → P4-B → P4-C → P4-D → P4-E → P4-F`

### P4-0 — P3 Closure & P4 Program Setup — Complete

Merged as PR #28.

### P4-A — Review Selection & Curation — Complete

Merged as PR #29 at
`3486146494076e9b513843b90ec44e504043729e`.

Delivered a temporary page-spanning Pick workflow over logical Selected:

```text
Selected
    ↓ direct temporary Pick Set
Keep Selection
    ↓
new Selected subset
```

The Pick Set and captured baseline are application-session temporary state only and
remain non-persistent. Pick membership is not source-residency, preload, cache, or
analysis authority.

### P4-B — Comparison Set Persistence — Active

Implementation branch: `feature/p4-b-comparison-set-persistence`.

P4-B persists a reusable **Comparison Set**, not a full application session.
The v1 external `.pixelscope` artifact stores only durable comparison intent:

- schema identity/version;
- ordered logical Selected source references;
- optional Active source reference;
- optional applicable Primary source reference;
- stable layout mode (`Auto`, `Single View`, `Multi View`);
- a resolved RAW profile only when that source already has deterministic profile
  data at save time.

The artifact does **not** persist the Registered catalog outside Selected, Current
Comparison Page/page offset, decoded sources/previews, Difference/source caches,
residency/LRU/protection, preload/workers/tokens, P4-A Pick state/baseline, derived
Split/Difference documents, ROI/Line/Plots state, Display Gain, window/dock geometry,
Recent history, or diagnostics.

Open reconstructs runtime through the normal registration/selection/layout paths.
Existing non-set Registered documents remain Registered. Selected becomes the
loadable saved members in saved order. Current Comparison Page is derived from the
restored Active position and existing fixed page-size semantics. Missing paths are
skipped with compact reporting; a zero-loadable or corrupt/incompatible artifact
leaves the current workspace unchanged.

P4-B v1 is a local deterministic workflow using normalized absolute source paths.
There is no fuzzy relocation, moved-file search, or automatic path repair. Settings
schema remains v5.

P4-B is not Complete until implementation, owner-local validation, independent
review, and merge are complete.

### P4-C — Recent Entries & Comparison Set Entry UX — Planned

P4-C answers how a user quickly re-enters recently opened work; it does not redefine
what a Comparison Set stores.

Planned entry kinds are explicit:

```text
image
folder
comparison_set
```

A bounded MRU history will reuse the existing Open Images, Open Folder, and P4-B
Comparison Set loader semantics. Recent history remains operational history, not
ApplicationSettings, Registered/Selected state, residency ownership, or preload
ownership.

### P4-D — Saved ROI & Analysis Workspace Productivity — Planned

Separate reusable saved ROI definitions from the current active ROI that feeds
analysis. Coordinate and ownership semantics must be explicit before persistence is
added.

### P4-E — Viewer Overlay & Export Productivity — Planned

Keep overlay presentation-only and make every export artifact explicit about whether
it represents native data, normalized Difference data, presentation, analysis
output, or workflow metadata.

### P4-F — Integration & Workflow Hardening — Planned

Harden P4-A through P4-E against the inherited P2/P3 source-residency, preload,
Difference, Display Gain, RAW-profile, request-identity, and Qt-lifetime contracts.

### Deferred / future extension

A full persistent application session is **not** P4-B. There is currently no proven
workflow need to serialize the entire PixelScope UI/runtime state. If such a need is
established later, it should be designed as a separate versioned feature rather than
expanding Comparison Set v1 implicitly.

Arbitrary-angle Line Profile remains deferred pending an explicit pixel-sampling and
coordinate-display contract.

## P5 — Remote IQA Platform

- remote submission/result workflow;
- server/job API;
- GPU worker;
- artifact, heatmap, and result comparison.

## P6 — Identity, Access & Remote Operations

- login/SSO;
- token/credential lifecycle;
- permission/access policy;
- operational administration.

## P7 — Release Engineering & Distribution

- exactly PyInstaller 5.7 `onedir`;
- portable ZIP;
- Inno Setup;
- clean-PC smoke testing;
- signing;
- update strategy;
- repeatable release process.
