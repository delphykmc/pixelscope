# UI implementation status

Status: P4 **Workflow & Session Productivity** is Complete through P4-F / PR #35.
P5 **Remote IQA Platform** is Active in P5-C / Draft PR #42. P5-B local Results UI
is merged; P5-C Setup/Jobs/Remote Open Result UI is implemented and under closeout.

Current merged baseline:
`ad3721e28b759e75d8e0f4a28b003a4dd22f0f4a`

## Current shell — implemented

- Main toolbar owns image-view/analysis actions.
- The dedicated presentation-control row owns Layout / Page / Display Gain /
  Selected N / Clear Selection / Keep Selection.
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
layer.

## P4 workflow UI — implemented

### Review Selection & Curation

Native source tiles expose direct Pick controls. Pick state is visually distinct from
Active and Primary. Picks persist across Comparison Pages, own no decode/residency or
analysis work, and are not persisted.

The presentation row exposes:

```text
Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection
```

Keep Selection is the only temporary-curation operation that changes logical
Selected.

### Session / Recent

Current File workflow includes:

```text
Open Images...
Open Folder...
Open Session...
Open Recent Images      >
Open Recent Folders     >
Open Recent Sessions    >
--------------------------
Save Session...
```

Session restore is a bounded staged reconstruction and does not expose runtime arrays
or cache state as persistent UI state.

### Difference lifecycle

Only explicit successful Calculate establishes active Difference state. Toolbar Diff
is visibility-only for that established result. Keep Selection tears Difference down
before Selected mutates. A cached map alone does not become an active Difference UI
result.

### Focused export

Implemented export/productivity controls include:

- Statistics CSV;
- Histogram CSV;
- Line Profile CSV;
- Difference metrics CSV / Copy;
- settled active Difference presentation PNG.

Export consumes already-established local result/presentation state.

## P5-B Results UI — Complete / merged PR #38

P5-B established the canonical non-modal IQA result workspace and controller.

Use **File > Open IQA Result...** or P5-C's explicit Jobs **Open Result** to enter the
same Results authority.

Implemented result behavior includes:

- schema-v2 summary-first open;
- Absolute measurements as the initial mode;
- N-way `variant_id` Reference switching independent from local Primary;
- stable variant ordering across Absolute/Relative presentation;
- background one-Scene-at-a-time Reference preparation;
- canonical Dataset/Scene relative reductions;
- rollback to last-valid presentation after deferred-grid failure;
- attribute hierarchy/table and Scene Trend;
- metadata-only Scene source cards;
- explicit historical schema-v1 read-only compatibility;
- no passive Files/Selected/Current Comparison Page/Difference/native-analysis/
  residency mutation.

The IQA title bar supports Float/Dock, Maximize/Restore, and Hide. Reset Workspace
Layout restores the normal docked/hidden baseline.

## P5-C Setup / Jobs UI — implemented in Draft PR #42

The current high-level structure is:

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
    └─ merged P5-B workspace
```

Native OS image/folder pickers may remain modal. IQA setup, pair preview, job
progress, and result exploration remain non-modal so the user can continue normal
PixelScope work.

### Current Pair — implemented

When the Current Comparison Page has exactly two eligible native documents, Setup
reuses those **underlying A/B documents**. The user is not forced to browse for the
same images again.

Current Pair eligibility/status is compact and blocks submission for wrong count,
missing Remote IQA configuration, non-native/unsupported input, RAW, or dimension
mismatch as applicable.

Primary, Active, tile reorder, Display Gain, Difference, Split Channels, and other
presentation state do not redefine A/B submission identity.

### Folder Pair — implemented

The user chooses Folder A and Folder B, then runs **Validate / Preview**.

Current behavior:

- immediate eligible files only;
- PNG/JPG/JPEG/BMP;
- no recursion or symlink input;
- deterministic Unicode-NFC lexical ordering;
- equal non-zero eligible counts;
- pair sorted items by index;
- exact original dimensions per pair;
- maximum 512 Scenes;
- validated preview shown before **Submit Folder Pair** becomes available.

Folder Pair does not eagerly register every batch image into Files/Selected.

### Jobs — implemented

Jobs shows locally tracked remote job ID, kind, state, progress, and bounded message.

The client polls the current REST job state. Completion does not force the Results
workspace to change.

- **Cancel** requests server cancellation for an applicable non-terminal job.
- **Open Result** is enabled only after succeeded/partial has a published logical
  result reference that resolves through current machine-local root settings.
- Open Result is explicit and delegates to P5-B; it never creates another result
  viewer/parser.

A transient terminal result-reference GET failure may recover automatically through
bounded retry while the row remains `succeeded`/`partial`. Create-job POST is not
blindly retried.

### PARTIAL UI — implemented

A valid PARTIAL result can show:

```text
Partial result · <successful> / <requested> Scenes succeeded
```

and a bounded diagnostics table for failed/cancelled Scene outcomes. Published
successful Scenes remain available in the normal P5-B result exploration UI.

## Remote IQA Settings UI — implemented

**Edit > Settings... > Remote IQA** owns:

```text
Server base URL
Shared-storage roots:
    Root ID
    Client path
Staging root
```

The UI explains that Root ID is the portable logical identity while Client path is
this machine's drive/UNC mapping. Server physical paths and credentials are not
entered as portable result identity.

The current typed application settings schema is v6.

## P5-C debug UI/harness — implemented, debug-only

`PIXELSCOPE_REMOTE_IQA_DEBUG` gates developer contract-validation surfaces.

- Setup may expose **Inspect JSON · DEBUG** for Current/Folder request inspection.
- Jobs may expose **Replay JSON · DEBUG** for bounded logical terminal-job replay.
- The replay path still requires explicit Open Result.
- Deterministic fake result generation and localhost HTTP fault-server scripts are
  developer tools, not normal release UI.

The localhost server performs no IQA computation. It exercises the production HTTP
client and returns logical references to known schema-v2 test artifacts.

## P5-C UI closeout still required

The high-level UI exists, but PR #42 remains Draft because underlying lifetime/
storage behavior still has merge blockers that can affect user-visible state:

- cross-process staging and symlink/junction containment;
- cancellation/shutdown while preparation/staging is physically running;
- duplicate in-flight submit prevention and explicit ambiguous-create handling;
- settings-change/result-path-resolution race;
- latest-head validation and independent whole-PR review.

The UX decision remains **no blind create POST retry** and **no automatic result
open**.

## Deferred UI from P4

Not current UI commitments:

- saved/named/multiple ROI manager;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile.

## P5-D UI direction — planned / blocked until P5-C merge

P5-D owns explicit source/spatial inspection rather than P5-C.

Planned boundary:

```text
selected IQA Scene
    ↓ explicit Inspect
logical root + source hash verification
    ↓
canonical local registration/selection of only that Scene's sources
    ↓
viewer-linked Scene navigation
    ↓
analysis grid → source → viewer mapping
    ↓
spatial overlay / block inspector
```

Passive IQA result selection continues not to mutate PixelScope Selected state. IQA
Reference remains independent from Primary.

A transient return point may restore the previous local comparison workspace. It is
not Session persistence. If P4-A temporary curation is active, Inspect must not
silently invalidate the captured Pick baseline.

The GPU result may use an approximately 2K analysis domain for 4K-class inputs, so
spatial overlay must use server-authored geometry metadata rather than assuming a
fixed scale. The overlay is not a Difference image and must not acquire Difference/
source/cache authority.

## Remaining P5 UI sequence

```text
P5-B Results workspace                    Complete
P5-C Setup / Jobs / shared-storage flow   Active closeout
P5-D source/spatial Inspect               Planned after P5-C
P5-E Recent/historical IQA productivity   Planned
P5-F real-server/performance hardening    Planned
```

P5-E may extend the same canonical result-open path with bounded Recent IQA Results.
P5-F owns real external-server/shared-storage integration and measured large-dataset
lifetime/performance tuning. Authentication/SSO/permission UI remains P6.
