# Architecture

This document records the current runtime and ownership architecture. Phase-specific
historical detail is retained in the completed execution plans and focused durable
contracts linked from `docs/ROADMAP.md`.

## Core boundaries

`io` discovers and decodes files into source arrays. `core.ImageDocument` owns native
source arrays, metadata, canonical preview data, generation state, and source-local
caches. `core` performs Bayer handling, display conversion, Statistics/Histogram,
Line Profile, and Difference math without Qt. `workers` runs expensive I/O/numerics in
bounded pools. `ui` renders presentation and emits interaction intent. `app.MainWindow`
owns the Registered catalog, ordered Selected set, Current Comparison Page derivation,
presentation orchestration, settings composition, load identity, source residency, and
window lifecycle.

Native `ImageDocument.source` remains authoritative for local analysis. Preview,
Display Gain, Split presentation, Difference presentation, IQA spatial overlays, and
IQA Provenance do not redefine native source identity.

## Local workspace ownership

The sole local image/runtime hierarchy is:

```text
Registered
    ↓ user selection
Selected                         # ordered logical set, may exceed 6
    ↓ Selected order + page offset
Current Comparison Page          # derived, max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`MainWindow.current_comparison_documents()` is the semantic authority for the bounded
comparison working set. `Analysis Working Set = Current Comparison Page`.

Current Comparison Page is consumed by Multi View, Single View page context,
Statistics, Histogram, Line Profile, selection-derived Difference inputs, ROI/Line
normalization, foreground page loading, current-page residency protection, and local
viewer slot mapping. Viewer slots are page-local `1..6`; a global Selected ordinal is
not a viewer slot.

Files registration and logical Selected membership have no six-item limit. Selected
membership alone is not generic source-residency protection. Current Comparison Page
plus correctness dependencies owns generic protection; off-page Selected/Picked sources
may be evicted and reloaded without losing logical identity.

## Input and RAW boundaries

Supported local image families remain:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

**Open Images...** and direct file D&D are selection-oriented. **Open Folder...** and
folder D&D are registration-oriented and do not change Selected/current page merely by
registering a dataset. Mixed D&D preserves both intents.

RAW profile resolution stays inside the common input path. Direct RAW open may resolve
same-basename JSON or prompt for profile metadata. Folder/session registration can keep
RAW unresolved until the source becomes a foreground current-page requirement.
Unresolved RAW is not speculatively preloaded.

`RawProfile` separates packing/container/effective depth/endian/alignment/dimensions/
stride/layout/Bayer/Black/White metadata. Decoding returns native Gray/Bayer mosaics.
RAW display remains presentation-only:

```text
display = anchor + gain * (source - anchor)
```

1× uses native effective full scale, gain >1 is Black-anchored, Bayer tuple Black uses
CFA-specific anchors, processing avoids a full-frame Black map and float64 promotion,
and White Level remains metadata. Native Statistics/Histogram/Line/Difference never
consume gained preview pixels.

## Display Gain

`core.display_transform` owns generic scalar-anchor affine display math. Ordinary
Gray/RGB use anchor 0; RGBA gains RGB while preserving canonical alpha; RAW supplies its
metadata-derived anchor policy. Difference has an independent presentation Gain and is
excluded from general Display Gain.

1× reuses canonical preview with no derived worker. Gain >1 uses already-resident source
and the bounded numerical pool. Request/document/source/generation/gain/visibility
identity rejects stale work. Derived gain buffers are presentation buffers, not source
residency.

## P4 curation, Session, and Recent

P4 temporary curation inserts no new source layer:

```text
Selected
    ↓ current page review
transient Pick Set
    ↓ Keep Selection
new Selected subset
```

Pick state is IDs only, owns no decode/residency/analysis work, and is not persisted.
**Keep Selection** is the only Pick operation that mutates Selected and is an
unconditional active-Difference reset boundary before the normal Selected mutation.
Difference cache entries remain generation-keyed and are not purged merely by curation.

Session v1 (`pixelscope-session`) persists durable local workspace intent but not runtime
arrays, caches, residency/preload/worker state, temporary Picks, generated Difference
results, running remote jobs, or IQA history/state. Legacy Comparison Set v1 remains
read-compatible.

P4-C Recent Images/Folders/Sessions are typed max-10 path MRUs and observer metadata.
They remain independent from P5-E Recent IQA Results.

## Settings

Frozen `ApplicationSettings` plus `SettingsRepository` own versioned application
preferences. Workspace geometry/session QSettings remain separate.

Current application-settings schema is v6. In addition to the prior local/runtime
settings it owns machine-local Remote IQA configuration:

```text
RemoteIqaSettings
    server_base_url
    storage_roots[] {
        storage_root_id
        client_path
    }
    staging_root_id
```

`storage_root_id` is portable client/server identity. `client_path` is machine-local.
Server physical paths and credentials are not persisted by PixelScope. P5-E Recent IQA
metadata is intentionally outside `ApplicationSettings` and therefore does not change
schema v6.

## Worker and stale-result lifecycle

Foreground image loading uses the existing max-two pool; preload uses a dedicated
max-one pool; local numerical/display work uses the bounded shared numerical pool.

Cancellation is advisory. Result acceptance is governed by generation/token/request
identity. Registration and off-page Selected/Pick membership alone do not decode
unrelated sources.

P2 preload remains predicted Folder Position `+1`, one position deep, and does not
become a Selected-wide or Comparison-Page-ahead preload system. Exact matching RUNNING
preload may be promoted logically to foreground without duplicate decode.

Remote IQA introduces feature-local workers but no new local source-residency owner.
P5-B Result loading, P5-C request/staging/polling, P5-D source verification/spatial work,
and P5-E historical locator resolution each have explicit generation/revision gates.

## Source residency

`ResidencyManager` owns exact native `source.nbytes` accounting, protected soft-budget
LRU planning, and bounded diagnostics; `MainWindow` owns actual document mutation.
Only unprotected resident sources are evicted. A protected required source may exceed
the soft budget.

Preview arrays, Qt textures, gain buffers, Difference maps, split derivatives, Pick
IDs, Session/Recent metadata, remote result metadata, IQA overlays, worker temporaries,
and process RSS are outside decoded-source accounting.

## Difference

`difference_compatibility()` owns family compatibility and native-vs-normalized domain.
Supported families are Gray↔Gray, RGB/RGBA↔RGB/RGBA, and same-CFA Bayer↔Bayer. Equal
effective bit depth uses native code-domain Difference; mixed depth normalizes each
source independently and stores canonical float32 absolute Difference in `[0,1]`.

The DifferencePanel remains the numerical/cache authority. Explicit **Calculate** is the
only path that establishes a new active Difference result. Toolbar Diff is visibility
only after that result exists. Display Gain, RAW Black/White presentation policy,
preview pixels, Pick state, Session/Recent, and Remote IQA do not redefine Difference
identity or math.

## Remote IQA numerical authority

P5-A schema v1 remains explicit historical/read-only compatibility. P5-A2 schema v2 is
the current executable result authority:

```text
manifest.json
    → iqa_result_reader.load_result() version dispatch
        ├─ v1 → historical Result
        └─ v2 → ResultV2 / PartialResultV2
                    ↓ explicit Scene demand
                load_grid_scene(scene_id)
                    ↓
                iqa_v2_math target/reference reduction
```

The governing rule is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 separates `variant_id`, concrete `source_id`, `scene_id`, and
`measurement_context_id`. Server-authored W/S1/S2/count/valid are measurement
authority. PixelScope owns pair-valid support, both power comparison modes, signed
target-minus-reference, quality orientation, and Dataset reduction.

Normal open is summary-first: manifest + summary only. Deferred Scene-grid loading owns
containment/materialization/numerical validation. COMPLETE and successful PARTIAL Scenes
obey the same full Scene invariants; failed/cancelled requested Scenes exist only in
PARTIAL `scene_outcomes`.

## P5-B canonical Results workspace — Complete

P5-B / PR #38 owns the one result parser/controller/workspace path:

```text
canonical versioned loader
    ↓
Absolute Dataset/Scene presentation
    ↓ optional Reference
bounded one-Scene-at-a-time grid preparation
    ↓
relative scalar projections
    ↓
Dataset Overview / hierarchy / Scene Trend
```

P5-B retains derived scalar Reference-preparation results rather than the raw grid
corpus. Passive browsing does not mutate Files, Selected, local Primary, native
analysis, Difference, source residency/preload, Session, or Picks.

## P5-C storage, submission, and Jobs — Complete

P5-C / PR #42 owns portable source/result location and Remote IQA submission.

Portable identity is always:

```text
storage_root_id + relative_path
```

Configured Windows/UNC paths are machine-local mappings. Sources outside configured
roots may be staged with SHA-256 content identity. P5-C owns resolved containment,
independently named temp publication, atomic final publication, and SHA-256 winner/reuse
verification.

Initial user submission is exactly two variants A/B. Current Pair consumes the two
underlying Current Comparison Page sources. Folder Pair is independent deterministic
batch preparation over immediate PNG/JPG/JPEG/BMP files and does not register/select/
decode the batch into the local workspace.

`HttpIqaJobClient` owns only the synchronous REST protocol boundary and always runs in
feature-local workers. Remote jobs remain server-owned and durable across PixelScope
close. Create POST is never blindly retried; status/result/cancel follow their safe
idempotent policies. Terminal success/partial never auto-opens Results.

Live storage-root changes are guarded by mapping revision and pending re-resolution so
old mapped paths cannot overwrite newer settings.

## P5-D viewer-linked Scene inspection — Complete

P5-D / PR #43 is merged in current `main@b086443d188eb9daae4bbf4f0faab3ff1d114f93`.
It is the only explicit bridge from an open schema-v2 Result into native local viewing:

```text
selected IQA Scene
    ↓ explicit Inspect in Viewer
P5-C logical-root resolution
    ↓
ordinary-image header + exact encoded-byte SHA/dimension/decode verification
    ↓ all unique sources succeed
canonical Files document generations
    ↓
Selected / Current Comparison Page / existing viewers
    ↓
vector spatial overlay + Block Inspector
```

Verification is all-or-nothing. Source missing/remap/hash/dimension/decode failures do
not make the server Result corrupt. Repeated variant bindings may intentionally share
one concrete source identity. First successful Inspect captures one transient Return
snapshot; newer local intent invalidates Return rather than being overwritten.

P5-D uses result/Scene/local-intent/settings/spatial generations and cancels/drops active
feature-local work on new Result open and shutdown. It does not introduce another source
registry, viewer stack, or residency owner.

## P5-E historical Result architecture — Active / Draft PR #44

P5-E composes **in front of** P5-B open while deliberately installing **after** P5-D:

```text
File > Open IQA Result...
Jobs > Open Result
File > Open Recent IQA Results
        ↓
P5-E locator + expected historical identity context
        ↓
P5-D new-result teardown
        ↓
P5-B canonical async loader / v1-v2 dispatch
        ↓
P5-E pre-presentation identity/mapping gate
        ↓
existing Results workspace
        ↓ optional
P5-D Inspect in Viewer
```

### Typed historical location

`remote.iqa_history` is Qt-free and owns two locator forms:

```text
LogicalIqaResultLocator(storage_root_id, relative_path)
LocalIqaResultLocator(absolute_path)
```

Logical is the portable production form. Reopen resolves it through current
`RemoteIqaSettings` and P5-C `resolve_result_reference()`, which remains root/path/
resolved-containment/result-directory authority. Manual successful schema-v2 opens under
configured roots canonicalize to the most-specific logical root. Jobs preserve the
server-published logical Result reference. Local absolute locators are machine-dependent
fallback for manual/out-of-root and schema-v1 Results.

### Recent IQA Results observer repository

`app.iqa_history.RecentIqaResultsRepository` persists independent observer metadata:

```text
QSettings key: recent/iqa_results
payload version: 1
max retained: 10
ordering: MRU
dedup: locator identity
```

It stores only typed locator + observed `result_id + schema_version`. Malformed/future
records are ignored within explicit bounds. This repository is not ApplicationSettings,
P4-C Recent, Session, source identity, or result-integrity authority.

### Canonical-open guard

`ui.iqa_historical_results.HistoricalIqaResultsController` wraps the already P5-D-wrapped
P5-B `open_result()` rather than adding a reader. A pending context is keyed to the
predicted/actual P5-B generation. The existing P5-B loader reads and validates the
artifact first. For Recent reopen, P5-E inspects the successful loaded result and rejects
an observed `result_id/schema_version` mismatch **before** invoking P5-B
`IqaWorkspaceWidget.set_model()`.

Thus an identity mismatch or stale logical-root mapping cannot replace the last valid
presented Result. No whole-result digest is added; structural/numerical integrity remains
the canonical result reader's responsibility.

Rapid A→B remains latest-open-wins because P5-B generation rejects the older callback.
P5-E keeps only the newest pending open context. Logical Recent resolution also captures
P5-C mapping revision; a remap before publish triggers fresh resolution or rejection.

### Result-only and Provenance

Historical Result open remains summary-first and does not stat/hash/decode all original
Scene sources. A valid server Result therefore stays browsable when native sources are
offline, unmapped, moved, replaced, or lack portable source location. Actual source
existence/containment/dimension/encoded-SHA/decode verification remains explicit P5-D
Inspect authority.

P5-E adds one passive **Provenance** page inside the existing Results tab set. Schema v2
shows Result identity/publication state, selected Scene measurement-context provenance,
per-variant source ID, optional storage root, relative path, source SHA-256, dimensions,
and current native-inspection status. The page never decodes source pixels or recomputes
IQA. Schema v1 is labelled historical/read-only and receives no synthetic v2 fields.
PARTIAL remains PARTIAL and existing failed/cancelled diagnostics remain the P5-B/P5-C
authority.

### Lifetime and Session boundary

New Result open reaches P5-D teardown before P5-B loading. Close cancels P5-E
feature-local logical-locator resolution, clears pending historical context, then
continues through P5-D/P5-B shutdown. Durable server jobs are never cancelled by this
path.

Session v1 is unchanged and carries no IQA locator, Result identity, Reference, Scene,
Provenance, Inspect, or Return state. Any future Session-IQA persistence requires an
explicit new Session schema/version decision.

Focused contract:
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md).

## Runtime diagnostics and release boundaries

`RuntimeDiagnosticsSnapshot` remains deterministic, bounded, sanitized, and
observation-only. The user surface is **Help > Copy Diagnostics**; no live diagnostics
monitor is introduced.

Canonical application icon assets and source-run Windows identity are package/runtime
concerns. PyInstaller 5.7 `onedir`, installer shortcuts/identity, signing, update, and
final distribution remain P7. Remote REST/client/result/history boundaries remain
independent from packaging. All current APIs target CPython 3.10.
