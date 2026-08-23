# UI implementation status

Status: P4 **Workflow & Session Productivity** is Complete through P4-F / PR #35.
P5 **Remote IQA Platform** is Active in P5-E **Historical Result Workflow** / Draft PR #44.
P5-B Results, P5-C Setup/Jobs/shared storage, and P5-D viewer-linked Scene inspection are
merged.

Current merged baseline:
`b086443d188eb9daae4bbf4f0faab3ff1d114f93`

Active P5-E contract:
[`../P5E_HISTORICAL_RESULTS.md`](../P5E_HISTORICAL_RESULTS.md).

Completed P5-D contract:
[`../P5D_VIEWER_INSPECTION.md`](../P5D_VIEWER_INSPECTION.md).

## Current shell — implemented

- Main toolbar owns image-view/analysis actions.
- The presentation-control row owns Layout / Page / Display Gain / Selected N /
  Clear Selection / Keep Selection.
- Files is the catalog/selection surface.
- Analysis contains Statistics and Difference.
- Plots contains Histogram and Line Profile with dock/floating persistence.
- One IQA dock contains Setup / Jobs / Results and follows the same float/dock/
  maximize/reset workspace pattern as Plots.
- File menu owns Open Images, Open Folder, Open Session, typed Recent
  Images/Folders/Sessions, Save Session, focused analysis exports,
  **Open IQA Result...**, and P5-E **Open Recent IQA Results**.
- There is no separate current Open/Save Comparison Set UI; legacy Comparison Set v1
  remains readable through Session open compatibility.

## Local workspace UI contract — implemented

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

- Registered is not capped by six.
- Selected may exceed six.
- Current Comparison Page is the maximum-six local analysis/viewing working set.
- `Analysis Working Set = Current Comparison Page`.
- viewer slots are page-local `1..6`.
- Open Images/direct-file D&D are selection-oriented.
- Open Folder/folder D&D are registration-oriented and do not replace Selected.
- Registered-but-unselected is valid.

Remote IQA Setup/Jobs/Results/Recent/Provenance does not add another local source or
analysis working-set layer. Only explicit successful P5-D **Inspect in Viewer** enters
the local hierarchy.

## P4 workflow UI — implemented

### Review Selection & Curation

Native source tiles expose direct Pick controls. Pick state is distinct from Active and
Primary. Picks persist across Comparison Pages, own no decode/residency or analysis work,
and are not persisted.

The presentation row exposes:

```text
Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection
```

Keep Selection is the only temporary-curation operation that commits Pick state to
logical Selected. P5-D refuses initial Inspect while a temporary Pick baseline is active.

### Session / Recent

Current File workflow includes Open Images, Open Folder, Open Session, typed Recent
Images/Folders/Sessions, and Save Session. Session restore remains a bounded staged
reconstruction and does not expose runtime arrays/cache state as persistent UI state.

P5-E does not extend Session v1. IQA Result locator/identity, IQA Reference, selected
IQA Scene, Provenance state, Inspect state, and Return state are not persisted in Session.

### Difference lifecycle

Only explicit successful Calculate establishes active Difference state. Toolbar Diff is
visibility-only for that established result. P5-D/P5-E do not add a Difference owner or
treat spatial/provenance data as Difference output.

### Focused export

Implemented exports include Statistics CSV, Histogram CSV, Line Profile CSV, Difference
metrics CSV/Copy, and settled active Difference presentation PNG. Export consumes
already-established local result/presentation state.

## P5-B Results UI — Complete / PR #38

P5-B owns the canonical non-modal IQA result workspace/controller.

All File, Jobs, and P5-E Recent opens converge on this same Results authority.

Implemented behavior includes:

- schema-v2 summary-first open;
- Absolute measurements as initial mode;
- N-way `variant_id` Reference switching independent from local Primary;
- background one-Scene-at-a-time Reference preparation;
- canonical Dataset/Scene relative reductions;
- rollback to last-valid presentation after deferred-grid failure;
- attribute hierarchy/table and Scene Trend;
- Scene source identity/path/hash cards;
- COMPLETE/PARTIAL diagnostics;
- historical schema-v1 read-only compatibility;
- passive browsing with no Files/Selected/Current Comparison Page/Difference/
  native-analysis/residency mutation.

The IQA title bar supports Float/Dock, Maximize/Restore, and Hide. Reset Workspace
Layout restores the normal docked/hidden baseline.

## P5-C Setup / Jobs UI — Complete / PR #42

High-level structure:

```text
IQA
├─ Setup
│   ├─ configuration status + Settings...
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
│   ├─ tracked job table
│   ├─ Cancel
│   └─ Open Result
└─ Results
    └─ P5-B workspace + P5-D Inspect + P5-E Provenance
```

Native OS image/folder pickers may remain modal. IQA setup, pair preview, job progress,
result exploration, history, and Scene inspection remain non-modal.

Current Pair uses exactly two eligible underlying Current Comparison Page documents.
Primary, Active, tile reorder, Display Gain, Difference, and Split presentation do not
redefine A/B submission identity.

Folder Pair uses immediate PNG/JPG/JPEG/BMP files, deterministic Unicode-NFC ordering,
equal non-zero counts, pair-by-index mapping, exact pair dimensions, no recursive or
symlink input, and maximum 512 Scenes. It does not eagerly register the batch into
Files/Selected.

Jobs shows locally tracked remote job identity/state/progress. Completion never forces
Results to change. Cancel requests server cancellation. Open Result is explicit. P5-E
observes successful Jobs open so the server-published logical Result locator is retained
for history rather than the current mapped client path.

Valid PARTIAL results show successful/requested Scene counts and bounded diagnostics for
failed/cancelled outcomes while successful Scenes remain explorable.

## Remote IQA Settings UI — Complete

**Edit > Settings... > Remote IQA** owns:

```text
Server base URL
Shared-storage roots:
    Root ID
    Client path
Staging root
```

Root ID is portable logical identity; Client path is machine-local drive/UNC mapping.
Typed application settings remain schema v6.

## P5-D Viewer-linked Scene Inspection — Complete / PR #43

P5-D adds one explicit Scene-to-native-viewer transition to the existing Results page.

```text
selected IQA Scene
    ↓ explicit Inspect in Viewer
logical root + dimensions + exact encoded-byte SHA verification
    ↓ all sources succeed
canonical local registration / Selected / Current Comparison Page
    ↓
existing Single/Multi ImageViewer
    ↓
vector spatial overlay + Block Inspector
    ↓ explicit Return
captured local Selected/page/Active/Primary/layout
```

Scene Trend contains:

- **Inspect in Viewer**;
- **Return**;
- **Spatial attribute** selector;
- compact Inspect status;
- spatial scale/mode legend;
- Block Inspector diagnostics;
- shared-source spatial-binding selection where multiple variants intentionally share
  one concrete native source.

Old schema-v2 Results without the additive source root locator remain result-readable
but cannot native-Inspect. Native source failures do not invalidate the server Result.

P5-D verifies every required source before local mutation and then uses ordinary
registration/Selected/residency/viewer paths. Newer local intent invalidates Return
rather than being overwritten. IQA Reference and local Primary remain independent.

Spatial overlays reuse schema-v2 W/S1/S2/count/valid and canonical geometry/math. They
are vector/block presentation, not a full-resolution image buffer or a second source
owner.

New Result open and shutdown cancel/drop P5-D feature-local verification/spatial work.

## P5-E Historical Result Workflow — Active / Draft PR #44

P5-E extends the **same** canonical result-open UI with historical discovery and passive
provenance.

### Open Recent IQA Results

File menu adds:

```text
Open Recent IQA Results
    <MRU result entries, max 10>
    ---------------------------
    Clear Recent IQA Results
```

History is independent from Recent Images/Folders/Sessions.

Each successful Result open records:

- a typed historical locator;
- observed `result_id`;
- observed `schema_version`.

Production logical entries display/retain `storage_root_id + relative_path`, not the
machine's mapped drive/UNC path. Manual out-of-root and schema-v1 entries may display a
machine-local absolute path.

Reopen resolves logical entries through current Remote IQA mappings. Missing/offline
entries are kept unless the user explicitly chooses Remove or Clear.

If the locator now resolves to a different `result_id/schema_version`, the reopen is
rejected before Results presentation changes. The last valid Result stays displayed.

### Result-only browsing

Recent or manual Result open does not verify all native Scene sources. Overview, Scene
Trend, PARTIAL diagnostics, and Provenance therefore remain usable when original source
files are offline/unmapped/missing. Native source verification stays explicit P5-D
Inspect behavior.

### Provenance page

The existing Results tab set gains **Provenance**.

For schema v2 it displays:

- Result ID/schema/COMPLETE-or-PARTIAL state;
- historical locator;
- selected Scene measurement-context provenance;
- per-variant source ID;
- published logical root when present;
- relative path;
- SHA-256;
- width/height;
- local native-inspection status.

The page does not decode native pixels and does not recompute IQA.

Schema v1 is explicitly labelled historical/read-only and does not invent v2 fields.

### P5-E lifecycle

P5-E is installed after P5-D. A new historical Result therefore consumes the same P5-D
new-result teardown before entering the P5-B loader. P5-B Result generation remains the
latest-open-wins authority; P5-E additionally rejects logical-locator work resolved
under an obsolete root-mapping revision.

Closing PixelScope cancels P5-E locator resolution/pending context only; durable remote
server jobs remain untouched.

## P5-E validation status

P5-E is **not Complete**. Focused automated tests have been added, but no exact-head CI
or local PASS has been observed in the implementation environment. Owner Windows manual
validation A–G and independent latest-head review remain pending. See
[`../P5E_HISTORICAL_RESULTS.md`](../P5E_HISTORICAL_RESULTS.md).

## Deferred UI from P4

Not current UI commitments:

- saved/named/multiple ROI manager;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile.

## Remaining P5 UI sequence

```text
P5-B Results workspace                    Complete
P5-C Setup / Jobs / shared-storage flow   Complete
P5-D source/spatial Inspect               Complete
P5-E Recent/historical IQA productivity   Active — Draft PR #44
P5-F real-server/performance hardening    Planned
```

P5-F owns real external-server/shared-storage compatibility and measured lifetime/
performance tuning. Authentication/SSO/permission UI remains P6.
