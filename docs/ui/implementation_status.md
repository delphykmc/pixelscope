# UI implementation status

Status: P4 **Workflow & Session Productivity** is Complete through P4-F / PR #35.
P5 **Remote IQA Platform** is complete through P5-F **Integration & Performance
Hardening**. P5-G **External GPU/SMB Validation & Closeout** remains deferred as the
final P5 gate until the environment is available. R **Repository Refactoring &
Validation Hardening** is the active behavior-preserving repository program.
P5-B local Results, P5-C Setup/Jobs/shared-storage UI, P5-D viewer-linked Scene
inspection, P5-E historical Results, and P5-F repository hardening are merged.

Current merged baseline:
`7c0d326fd2a8ff767ac916d29af1c7d5ee44abd6`

R1 application composition and R2 result-pool ownership are merged. R3-A removes an
unconnected pre-P5 Remote scaffold and adds no UI behavior.

Completed P5-F characterization:
[`../P5F_INTEGRATION_CHARACTERIZATION.md`](../P5F_INTEGRATION_CHARACTERIZATION.md).

Completed P5-E contract:
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
- Registered-but-unselected is a valid workspace state.

Remote IQA Setup/Jobs/Results/Recent/Provenance does not add another local
source/analysis working-set layer. P5-D invokes that local hierarchy only after
explicit, successful Scene Inspect verification.

## P4 workflow UI — implemented

### Review Selection & Curation

Native source tiles expose direct Pick controls. Pick state is visually distinct from
Active and Primary. Picks persist across Comparison Pages, own no decode/residency or
analysis work, and are not persisted.

The presentation row exposes:

```text
Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection
```

Keep Selection is the only temporary-curation operation that commits Pick state to
logical Selected. P5-D therefore refuses Inspect while a temporary Pick baseline is
active.

### Session / Recent

Current File workflow includes Open Images, Open Folder, Open Session, typed Recent
Images/Folders/Sessions, and Save Session. Session restore remains a bounded staged
reconstruction and does not expose runtime arrays/cache state as persistent UI state.

P5-D Return state is transient and is not added to Session v1. P5-E also does not add
IQA Result locator/identity, IQA Reference, selected Scene, Provenance, or Inspect state
to Session v1.

### Difference lifecycle

Only explicit successful Calculate establishes active Difference state. Toolbar Diff
is visibility-only for that established result. Selection/curation changes continue to
obey the canonical Difference teardown/recalculation lifecycle. P5-D/P5-E do not add a
Difference owner or treat spatial/provenance presentation as Difference output.

### Focused export

Implemented export/productivity controls include Statistics CSV, Histogram CSV, Line
Profile CSV, Difference metrics CSV/Copy, and settled active Difference presentation
PNG. Export consumes already-established local result/presentation state.

## P5-B Results UI — Complete / PR #38

P5-B owns the canonical non-modal IQA result workspace/controller.

Use **File > Open IQA Result...**, P5-C Jobs **Open Result**, or P5-E Recent IQA Results
to enter the same Results authority.

Implemented behavior:

- schema-v2 summary-first open;
- Absolute measurements as the initial mode;
- N-way `variant_id` Reference switching independent from local Primary;
- stable variant ordering across Absolute/Relative presentation;
- background one-Scene-at-a-time Reference preparation;
- canonical Dataset/Scene relative reductions;
- rollback to last-valid presentation after deferred-grid failure;
- attribute hierarchy/table and Scene Trend;
- Scene source identity/path/hash cards;
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
    └─ P5-B workspace + P5-D Inspect controls + P5-E Provenance
```

Native OS image/folder pickers may remain modal. IQA setup, pair preview, job progress,
result exploration, and Scene inspection controls remain non-modal.

### Current Pair

When the Current Comparison Page has exactly two eligible native documents, Setup
reuses those underlying A/B documents. Primary, Active, tile reorder, Display Gain,
Difference, and Split presentation do not redefine A/B submission identity.

### Folder Pair

Validate / Preview uses immediate PNG/JPG/JPEG/BMP files, no recursion/symlink input,
deterministic Unicode-NFC ordering, equal non-zero counts, pair-by-index mapping,
exact pair dimensions, and maximum 512 Scenes. It does not eagerly register the batch
into Files/Selected.

### Jobs

Jobs shows locally tracked remote job identity/state/progress. Completion never forces
Results to change. Cancel requests server cancellation. Open Result is explicit and
uses the canonical P5-B path. Create POST is not blindly retried; terminal result
reference recovery is bounded. P5-E observes a successful Jobs open and retains the
server-published logical Result locator rather than the current mapped client path.

### PARTIAL

Valid PARTIAL results show successful/requested Scene counts and bounded diagnostics
for failed/cancelled outcomes while published successful Scenes remain explorable.

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
The typed application settings schema is v6.

## P5-C debug UI/harness — Complete, debug-only

`PIXELSCOPE_REMOTE_IQA_DEBUG` gates Request Inspector, Replay JSON, deterministic result
generation, and localhost HTTP fault tooling. Those surfaces exercise production client
contracts but are not the GPU server implementation.

## P5-D Viewer-linked Scene Inspection — Complete / PR #43

P5-D adds one explicit Scene-to-native-viewer transition to the existing Results page.

```text
selected IQA Scene
    ↓ explicit Inspect in Viewer
logical root + dimensions + source hash verification
    ↓ all sources succeed
canonical local registration / Selected / Current Comparison Page
    ↓
existing Single/Multi ImageViewer
    ↓
vector spatial overlay + Block Inspector
    ↓ explicit Return
captured local Selected/page/Active/Primary/layout
```

### Inspect controls

Scene Trend includes a P5-D panel with:

- **Inspect in Viewer**;
- **Return**;
- **Spatial attribute** selector;
- compact Inspect status;
- spatial scale/mode legend;
- selectable Block Inspector diagnostics.

Inspect availability is explicit:

- schema v2 required;
- a Scene must be selected;
- P4-A temporary Picks must not be active;
- all Scene sources need published logical locators resolvable by current settings;
- native Inspect supports at most six variants and never truncates extras.

Old schema-v2 artifacts without the additive source root locator remain result-readable
but cannot native-Inspect.

### Source transition

Before any local mutation P5-D verifies every required source. A failure keeps the
current local comparison intact. A valid Scene then uses the ordinary registration and
Selected paths, reusing already-Registered source documents.

IQA Scene source order becomes the requested local comparison order. No second Files
list or viewer stack exists.

### Return UI

The first successful Inspect captures one transient local Return point. Linked Scene
changes keep the first target.

Return restores exact Selected order, Comparison Page, layout, applicable Primary, and
actual Active presentation. If the user makes a newer non-IQA Selected/Files/layout/
Primary choice, Return is disabled/invalidated rather than overwriting that newer
intent.

### Reference / Primary

IQA **Reference** continues to control IQA target/reference math. Local **Primary**
continues to control viewer presentation/reference priority. They do not rewrite each
other.

### Spatial overlay

For the chosen spatial attribute:

- Absolute displays valid per-cell `S1/W`;
- Relative power displays raw target/reference dB using canonical schema-v2 epsilon
  handling;
- Relative signed displays raw target-reference delta;
- invalid/pair-invalid cells are not painted as valid zero;
- one shared scale covers currently displayed Scene variants.

The overlay is a vector `QGraphicsItem` on each existing viewer ViewBox. It does not
allocate a full-resolution heatmap image and does not become source/residency/cache
ownership.

Drawing and Block Inspector hit-testing share the same schema-v2 affine/grid geometry,
including non-zero origins, non-integer transforms, valid rectangles, and discarded
borders.

Block Inspector reports Scene/attribute/variant/source, row/column, validity,
W/S1/S2/count, mean, optional Reference/pair/raw-relative value, analysis bounds, and
source polygon.

### Async presentation safety

Source verification and spatial grid preparation use bounded workers. P5-F assigns
P5-B Result/Reference, P5-D verification/spatial, and P5-E historical resolver work to
a separate max-two Remote IQA pool so slow remote/storage work does not consume the
local Statistics/Difference pool. Rapid Scene/attribute/Reference changes, new Result
open, and shutdown retain the existing stale/cancel guards.

## P5-D validation status

P5-D completed its exact-head automated/manual/review gates and merged as PR #43 at
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93`. Its validation evidence is historical
P5-D evidence and is not inferred as P5-F validation.

## P5-E Historical Result Workflow — Complete / PR #44

P5-E extends the same P5-B Results authority with:

- **Open Recent IQA Results**, max 10, MRU, and locator dedup independent from existing
  Recent Images/Folders/Sessions;
- server-published `storage_root_id + relative_path` history for Jobs;
- manual schema-v2 logical-history promotion only when the P5-C resolver reproduces the
  same canonical opened Result directory, otherwise Local fallback;
- pre-presentation `result_id + schema_version` identity checking;
- Result-only browsing when native sources are unavailable;
- passive **Provenance** inside the existing Results workspace;
- explicit schema-v1 historical/read-only presentation;
- a feature-local resolver generation so delayed logical Recent resolution cannot
  override a newer File/Jobs/Recent Result-open intent;
- immediate Provenance refresh after the existing live Remote IQA settings-change chain.

P5-E remains passive with respect to Files/Selected/Current Comparison Page until the
existing P5-D **Inspect in Viewer** transition is explicitly invoked.

P5-E merged as PR #44 at
`main@6a0a334d61a7495b9c3433edfcbd537c8df59468`. Its validation evidence is historical
P5-E evidence and is not inferred as P5-F validation. See
[`../P5E_HISTORICAL_RESULTS.md`](../P5E_HISTORICAL_RESULTS.md).

## P5-F Integration & Performance Hardening — Complete / PR #45

P5-F makes no new user-facing IQA workspace. It hardens the existing composition by:

- isolating Remote IQA Result/Reference/Inspect/history file work from the established
  local Statistics/Difference analysis executor with a separate fixed max-two pool;
- retaining the existing separate max-two P5-C job-operation executor;
- reusing `HttpIqaJobClient` connection pools through **lazy physical checkout**: merely
  queuing an operation creates no physical client, and checkout happens only inside the
  executing worker's first HTTP operation;
- preserving CREATE no-blind-retry, one-poll-in-flight, terminal-state, server-owned
  cancel-race, result-reference, and durable-job-on-close semantics;
- extending **Help > Copy Diagnostics** with bounded Remote IQA worker/HTTP lifetime
  counters rather than adding another diagnostics UI;
- providing developer compatibility/result-characterization probes;
- adding production composition, four-job/max-two-worker shutdown, blocking-I/O
  coexistence, and structural request coverage through 300 Scenes.

No raw-grid cache, grid preload, adaptive polling, generalized HTTP retry, new
performance Settings, or optional detail-artifact viewer is introduced because current
repository evidence does not justify those as permanent product behavior.

Historical exact-head owner validation and independent review disposition are recorded
in the characterization document. Full pytest was not claimed PASS: it reported 925
passed, 1 skipped, and three Windows offscreen Qt/pyqtgraph failures reproduced on the
base. P5-F merged as PR #45 at
`main@6634447fc3c48545a2482718dd3f444928806218`. No GitHub Actions workflow was added.

Real external GPU/SMB validation remains unobserved and is explicitly assigned to P5-G.
Full evidence is in
[`../P5F_INTEGRATION_CHARACTERIZATION.md`](../P5F_INTEGRATION_CHARACTERIZATION.md).

## P5-G External GPU/SMB Validation & Closeout — Deferred

P5-G adds no new UI by default. It is the final P5 environment-validation gate and will
use the existing Setup/Jobs/Results/Recent/Inspect UI against the real external GPU
service and mapped/shared storage when that environment becomes available.

Only observed external evidence may justify follow-up hardening. P5-G, not P5-F merge,
marks the overall P5 program Complete and activates P6.

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
P5-E Recent/historical IQA productivity   Complete — PR #44
P5-F integration/performance hardening    Complete — PR #45
R repository/validation hardening         Active — behavior preserving
P5-G external GPU/SMB validation          Deferred — pending environment access
```

P5 remains Active through P5-G. Authentication/SSO/permission UI remains P6, which
becomes the active/next product program only after the real external P5 gate and final
closeout. R adds no UI feature.
