# UI implementation status

Status: P4 **Workflow & Session Productivity** is Complete through P4-F / PR #35.
P5 **Remote IQA Platform** is Active in P5-D **Viewer-linked Scene Inspection**.
P5-B local Results and P5-C Setup/Jobs/shared-storage UI are merged.

Current merged baseline:
`24b328d02c0cd56fb79920e069af06d6e4cb706f`

Active P5-D contract:
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
  Images/Folders/Sessions, Save Session, focused analysis exports, and
  **Open IQA Result...**.
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

Remote IQA Setup/Jobs/Results does not add another local source/analysis working-set
layer. P5-D invokes that local hierarchy only after explicit, successful Scene Inspect
verification.

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

P5-D Return state is transient and is not added to Session v1.

### Difference lifecycle

Only explicit successful Calculate establishes active Difference state. Toolbar Diff
is visibility-only for that established result. Selection/curation changes continue to
obey the canonical Difference teardown/recalculation lifecycle. P5-D does not add a
Difference owner or treat the spatial overlay as Difference output.

### Focused export

Implemented export/productivity controls include Statistics CSV, Histogram CSV, Line
Profile CSV, Difference metrics CSV/Copy, and settled active Difference presentation
PNG. Export consumes already-established local result/presentation state.

## P5-B Results UI — Complete / PR #38

P5-B owns the canonical non-modal IQA result workspace/controller.

Use **File > Open IQA Result...** or P5-C Jobs **Open Result** to enter the same Results
authority.

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
    └─ P5-B workspace + P5-D Inspect controls
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
reference recovery is bounded.

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

## P5-D Viewer-linked Scene Inspection — Active implementation

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

Source verification and spatial grid preparation use bounded feature-local workers.
Rapid Scene/attribute/Reference changes, new Result open, and shutdown reject/cancel
stale feature-local work. A stale callback cannot newly mutate the local workspace.

## P5-D validation status

The implementation is not yet marked Complete. Exact-head focused/full validation and
owner Windows manual validation remain required. See
[`../P5D_VIEWER_INSPECTION.md`](../P5D_VIEWER_INSPECTION.md) for the automated and
manual matrices.

## Deferred UI from P4

Not current UI commitments:

- saved/named/multiple ROI manager;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile.

## Remaining P5 UI sequence

```text
P5-B Results workspace                    Complete
P5-C Setup / Jobs / shared-storage flow   Complete
P5-D source/spatial Inspect               Active
P5-E Recent/historical IQA productivity   Planned
P5-F real-server/performance hardening    Planned
```

P5-E may extend the same canonical result-open path with bounded Recent IQA Results.
P5-F owns real external-server/shared-storage integration and measured large-dataset
lifetime/performance tuning. Authentication/SSO/permission UI remains P6.
