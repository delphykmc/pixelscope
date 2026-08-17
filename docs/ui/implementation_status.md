# UI implementation status

Status: P4 **Workflow & Session Productivity** is Complete through P4-F / PR #35.
P5 **Remote IQA Platform** is Active in P5-0 planning only. No P5 runtime/UI control
has been implemented yet.

Current merged baseline:
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`

## Current shell — implemented

- Main toolbar owns image-view/analysis actions.
- The dedicated presentation-control row owns Layout / Page / Display Gain /
  Selected N / Clear Selection / Keep Selection.
- Files is the catalog/selection surface.
- Analysis contains Statistics and Difference.
- Plots contains Histogram and Line Profile with dock/floating persistence.
- File menu owns Open Images, Open Folder, Open Session, typed Recent
  Images/Folders/Sessions, Save Session, and focused analysis exports.
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

## Deferred UI from P4

Not current UI commitments:

- saved/named/multiple ROI manager;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile.

## P5 planned UI direction — not implemented

P5 adds a non-modal **IQA workspace/dock**, not a large custom modal workflow.

Planned high-level structure:

```text
IQA
├─ Setup
│   ├─ Current Pair
│   └─ Folder Pair
├─ Jobs
└─ Results
```

Native OS image/folder pickers may remain modal. IQA setup state, pair preview, job
progress, and result exploration remain non-modal so the user can continue normal
PixelScope work.

### Planned Current Pair UX

When the current local comparison has exactly two eligible native sources, IQA Setup
will reuse those paths directly. The user should not be forced to browse for the same
images again.

No current-pair IQA control exists yet.

### Planned Folder Pair UX

P5 v1 will support two-folder batch setup:

- choose Folder A and Folder B;
- deterministically sort the supported RGB-family inputs;
- show the actual index-based Pair Preview;
- block submission when counts differ;
- keep semantic pairing responsibility with the user;
- submit the explicit Scene list rather than eagerly registering every batch image.

No batch IQA setup UI exists yet.

### Planned Jobs UX

Remote batch work is non-modal. Jobs should show at least state and useful progress
such as completed/total sources when the server exposes it. Completion should not
forcibly replace the current local workspace.

The P5 v1 transport plan uses polling rather than requiring WebSocket progress.

No IQA Jobs UI exists yet.

### Planned Results UX

Result exploration is hierarchical:

```text
Job / dataset
    ↓
10-attribute overview
    ↓
selected attribute trend / outliers
    ↓
selected scene
    ↓
spatial grid comparison
    ↓
block inspector
```

The planned overview combines an Attribute × Scene view with a selected-attribute
trend/outlier view. The UI must distinguish the server's two official aggregation
modes:

- ratio of weighted means;
- mean of grid log-ratios.

Signed Luma/Chroma bias is displayed as signed-value comparison rather than ordinary
dB quality direction.

No IQA Results UI exists yet.

### Planned passive browse / Inspect boundary

Passive IQA result selection must not mutate PixelScope Selected state.

An explicit **Inspect Pair** operation will load/register only the selected Scene pair
through the inherited canonical local path and then link Scene navigation to the
existing viewer. IQA Reference remains separate from Primary.

A transient return point may restore the previous local comparison workspace. It is
not Session persistence.

If P4-A temporary curation is active, P5 v1 should prevent an Inspect operation that
would silently invalidate the Pick baseline unless a later explicit conflict policy
is designed.

### Planned spatial overlay

The GPU produces results in an approximately 2K remote analysis domain for 4K-class
inputs. IQA grid overlay must therefore use server metadata to map:

```text
remote grid
→ remote analysis coordinate
→ original source coordinate
→ existing viewer transform
```

The overlay should be a lightweight viewer/grid layer driven by compact scene data;
it is not a Difference image and must not acquire Difference/source/cache authority.

## P5 implementation order

UI implementation begins only after P5-A establishes deterministic production-shaped
result fixtures and Qt-free domain/parser behavior.

Planned sequence:

- P5-A: contract fixtures + IQA domain, no production UI;
- P5-B: IQA workspace + local result overview/trends from fixtures;
- P5-C: Current Pair / Folder Pair submission + shared storage + HTTP jobs;
- P5-D: viewer-linked Inspect Pair / grid overlay / block inspector;
- P5-E: Open/Recent historical IQA Results;
- P5-F: real-server integration and large-dataset/lifetime hardening.

This ordering intentionally validates result semantics and user navigation before the
live GPU interface is allowed to shape the UI.