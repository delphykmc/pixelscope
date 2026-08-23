# PixelScope product specification

This document describes the current product behavior. Numerical/transport details for
Remote IQA are governed by `REMOTE_IQA_CONTRACT.md` and `REMOTE_IQA_V2_SPEC.md`.

## Product purpose

PixelScope is a Windows desktop engineering tool for fast local image inspection,
comparison, RAW analysis, Difference review, workflow/session productivity, and optional
external Remote IQA evaluation.

The local workflow remains primary. Remote IQA is an optional parallel workflow and does
not replace local source ownership.

## Local workspace model

PixelScope distinguishes:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page       # maximum 6
    ↓
Presented
    ↓
Resident when required
```

- Registered: Files/catalog membership.
- Selected: ordered logical comparison set; may exceed six.
- Current Comparison Page: derived current working subset, maximum six.
- Presented: current viewer representation.
- Resident: decoded native source retained when required.

`Analysis Working Set = Current Comparison Page`.

## Local input

Supported local files:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

### Open Images

**File > Open Images...** is selection-oriented. Supported selected files are registered
and become the ordered Selected set. More than six remain Selected and are paged in
six-image Comparison Pages.

### Open Folder

**File > Open Folder...** is registration-oriented. Supported immediate contents are
added to Files without changing the current Selected/current page merely because a new
dataset was registered. Multi-folder registration remains available through folder D&D.

### RAW

RAW uses the same top-level image-open workflow. Same-basename JSON profile metadata may
be used; unresolved RAW may prompt when it becomes a foreground requirement. RAW native
source remains analysis authority. Display Gain never changes native analysis data.

## Viewer and navigation

PixelScope supports Single/Multi View with fixed comparison geometry. For large Selected
sets, the Current Comparison Page remains maximum six with six-slot page semantics.

- Left/Right: previous/next Selected image.
- Ctrl+Left/Ctrl+Right: previous/next Comparison Page when available.
- PageUp/PageDown: Folder Position workflow, not Comparison Page navigation.
- number keys 1..6: page-local viewer slots.

Primary is page-local and independent from logical Selected ordering.

## Local analysis

Current local analysis includes:

- Statistics;
- Histogram;
- Line Profile;
- Difference;
- ROI;
- Split Channels;
- Display Gain presentation.

Difference supports Gray, RGB/RGBA, and compatible Bayer families. Mixed effective bit
depth uses normalized float32 Difference; equal depth uses native code-domain Difference.
Explicit **Calculate** establishes the active Difference. Toolbar Diff thereafter controls
visibility only.

Display Gain is presentation-only. Ordinary Gray/RGB use zero anchor; RAW gain >1 uses
Black-anchored display semantics. Difference has its own presentation gain.

## Review curation

Eligible native Multi View tiles expose **Pick**. Pick is temporary source-ID membership
and is distinct from Active and Primary.

The presentation controls expose:

```text
Selected N | Clear Selection | Keep Selection
```

Keep Selection commits the picked subset to logical Selected in baseline order. Pick
state is not persisted and does not own source residency or analysis work.

## Session and Recent local workflow

New `.pixelscope` saves use Session v1. Session persists durable local workspace intent,
not runtime arrays/caches/workers/residency. Legacy Comparison Set v1 remains readable.

File menu provides typed Recent:

- Open Recent Images;
- Open Recent Folders;
- Open Recent Sessions.

These remain separate from P5-E Recent IQA Results.

## Focused export

Current export surfaces consume already-established analysis/result state. They do not
create new numerical authority. Current exports include Statistics/Histogram/Line
Profile CSV and applicable Difference metrics/presentation export.

## Remote IQA product flow

P5 connects local inspection to an external GPU IQA service:

```text
fast local inspection
    ↓ optional
submit Current Pair or deterministic Folder Pair
    ↓
non-modal durable remote job
    ↓
continue local work
    ↓
explicit Open Result
    ↓
Absolute / Relative Dataset Overview
    ↓
Scene Trend / outliers
    ↓ optional
Inspect in Viewer
    ↓
verified native Scene sources + spatial inspection
    ↓ optional
Return
```

P5-E adds durable historical reopen without rerunning a job:

```text
successful Result open
    ↓
Recent IQA Results entry
    ↓ later
logical/local reopen
    ↓
canonical Results workspace
```

## Remote IQA configuration

**Edit > Settings... > Remote IQA** owns:

- server base URL;
- one or more shared-storage mappings:
  - Root ID (`storage_root_id`);
  - machine-local Client path;
- optional Staging root.

Portable source/result location is Root ID + relative path. A client drive/UNC path is
machine-local configuration and is not portable request/result/history identity.

## Remote IQA submission

Initial user-facing submission is exactly two variants A/B.

### Current Pair

Current Pair requires exactly two eligible underlying Current Comparison Page source
images. A/B order follows the underlying page/source order and is independent from
Primary, Active, view reorder, Display Gain, Difference, or Split presentation.

### Folder Pair

Folder Pair is deterministic batch preparation over immediate eligible files:

- PNG/JPG/JPEG/BMP only;
- no RAW conversion;
- non-recursive;
- no symlink inputs;
- deterministic Unicode-NFC lexical ordering;
- equal non-zero eligible counts;
- pair-by-index;
- equal dimensions within each pair;
- maximum 512 Scenes.

Folder Pair does not register/select/decode the entire remote batch into the local
workspace.

## Remote Jobs

Jobs are non-modal and server-owned. States include queued/preparing/extracting/
aggregating/writing/succeeded/partial/failed/cancelled.

Completion never automatically replaces Results. **Open Result** is explicit. Only
terminal succeeded/partial jobs can expose an immutable Result reference.

Create-job POST is not blindly retried after ambiguous failure. Safe idempotent result
reference recovery may use bounded retry.

## IQA Results workspace

All Result open sources converge on the same P5-B canonical loader/workspace:

- **File > Open IQA Result...**;
- Jobs **Open Result**;
- P5-E **Open Recent IQA Results**.

Schema v2 opens summary-first and defaults to Absolute measurements. Reference selection
is local IQA state independent from image Primary. Relative preparation loads bounded
Scene grids asynchronously. Failed deferred preparation returns to last-valid
presentation.

The Results workspace exposes Dataset Overview, hierarchy/table, Scene Trend, source
metadata, COMPLETE/PARTIAL diagnostics, P5-D inspection controls, and P5-E Provenance.

Schema v1 remains explicit historical/read-only compatibility and is not silently
upgraded to v2 semantics.

## COMPLETE and PARTIAL

A COMPLETE schema-v2 Result contains all fully published successful Scenes.

A PARTIAL Result contains at least one successful Scene plus explicit failed/cancelled
requested-Scene outcomes. Only fully published successful Scenes appear in `scenes[]`.
Successful Scenes remain normally explorable and inspectable when source verification
permits. Failed/cancelled diagnostics remain visible; P5-E history does not synthesize
missing Scenes or rewrite PARTIAL as COMPLETE.

## Viewer-linked IQA inspection

Passive Results browsing never mutates local Selected.

For schema-v2, explicit **Inspect in Viewer** may verify and show the selected Scene in
the existing local viewer. P5-D requires all required unique sources to resolve and
verify before local mutation. Verification includes portable root containment,
ordinary-image eligibility, dimensions, exact encoded-byte SHA-256, and decode.

Source missing/remap/hash/dimension/decode failure affects Inspect availability/success,
not the integrity of an otherwise valid server Result.

Repeated variant bindings may share one concrete source. PixelScope retains one canonical
local source/document identity while preserving IQA variant aliases.

First successful Inspect captures one transient Return target. Newer local Selected/
Files/layout/Primary/Pick intent invalidates Return instead of being overwritten.

Spatial inspection uses existing schema-v2 geometry and W/S1/S2/count/valid data. Overlay
is vector/block presentation in the existing viewer, not a second image/source registry.

## P5-E Historical Result Workflow — Active / Draft PR #44

### Open Recent IQA Results

File menu adds **Open Recent IQA Results**.

History behavior:

- dedicated independent metadata;
- maximum 10 entries;
- MRU ordering;
- deduplication by historical locator;
- successful File/Jobs/Recent opens record;
- failed/incompatible/corrupt/identity-mismatch opens do not record;
- **Clear Recent IQA Results** affects only IQA history;
- missing/offline/remapped entries remain until explicit Remove/Clear.

P4 Recent Images/Folders/Sessions are unchanged.

### Historical locator

A production historical Result locator is exactly:

```text
storage_root_id + relative_path
```

It is resolved through the current machine's Remote IQA mapping each time it is reopened.
Jobs retain the published logical Result locator. Successful manual schema-v2 opens under
configured roots canonicalize to the most-specific logical root.

A machine-local absolute historical locator is permitted for manual/out-of-root and
schema-v1 Results. It is explicitly not portable identity.

### Historical identity and replacement detection

Recent records observed:

```text
result_id + schema_version
```

No second whole-Result digest is introduced. On Recent reopen, the existing canonical
reader validates the artifact. P5-E then verifies that observed identity matches the
stored historical identity **before** replacing the presented Result.

If the location now contains another Result identity, the reopen is rejected, the
previous valid Result remains displayed, and the Recent entry is kept unless explicitly
removed.

### Result-only mode

A valid Result remains useful even if original source images are unavailable. Result
open therefore does not stat/hash/decode all native Scene sources.

Overview, hierarchy, Scene Trend, PARTIAL diagnostics, and Provenance remain browseable
while original images are offline/unmapped/missing/changed. Native verification is only
performed on explicit P5-D Inspect.

### Provenance

The existing Results workspace includes **Provenance**.

Schema v2 Provenance displays published metadata including:

- Result ID;
- schema version;
- COMPLETE/PARTIAL publication state;
- historical locator;
- selected Scene `measurement_context_id`;
- representative/preprocessing/model/weighting/geometry provenance IDs;
- per-variant source ID;
- published Root ID when present;
- source relative path;
- source SHA-256;
- width/height;
- current native-inspection status.

Provenance does not decode source pixels and does not recompute IQA.

Schema v1 is explicitly labelled historical/read-only and displays only metadata actually
present in v1. It does not invent v2 measurement-context/root/absolute-source fields.

### Stale and close behavior

P5-E reuses P5-B Result generations: rapid A→B accepts only the latest Result callback.
Logical Recent resolution also uses P5-C root-mapping revision so old mapping work cannot
replace the current Result after settings change.

Every new Result open consumes P5-D new-result teardown before P5-B loading. Closing the
window cancels feature-local historical resolver/pending state and then continues normal
P5-D/P5-B teardown. Durable remote jobs are not cancelled by closing PixelScope.

## Session boundary for IQA

Session v1 remains unchanged. It does not persist:

- Remote IQA job state;
- IQA Result locator/identity;
- IQA Reference;
- selected IQA Scene;
- Provenance UI state;
- Inspect/Return state;
- remote numerical arrays.

Any future Session-carried IQA state requires an explicit new Session schema/version
decision.

## Deferred / future scope

P5-F is planned for real external-server compatibility and measured performance/lifetime
hardening:

1. real GPU server compatibility;
2. SMB/network/grid performance characterization;
3. cache/HTTP/retry/backoff tuning;
4. stress/failure/lifecycle hardening;
5. optional detail characterization and P5 closure.

P6 owns login/SSO/token/permission/admin lifecycle. P7 owns packaging/signing/update and
final distribution.

P4-deferred Saved/named/multiple ROI, Alpha Overlay/Flicker/Wipe, and arbitrary-angle Line
Profile remain outside current P5 scope.

## Current phase status

Current merged main:
`b086443d188eb9daae4bbf4f0faab3ff1d114f93` — P5-D Complete.

P5-E is Active in Draft PR #44 and is not Complete until exact-head automated/full
validation, owner Windows manual validation A–G, independent whole-PR review, and owner
merge approval are complete.
