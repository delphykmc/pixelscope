# PixelScope current state

Snapshot date: 2026-08-11

Current merged baseline / P4-A PR #29 merge commit:
`3486146494076e9b513843b90ec44e504043729e`

P4-A Review Selection & Curation is Complete. P4-B Comparison Set Persistence is
active on `feature/p4-b-comparison-set-persistence` and is not Complete until owner
validation, independent review, and merge.

## Runtime ownership model

The authoritative P2/P3 hierarchy remains:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + derived page offset
Current Comparison Page        # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

- Registered is the Files catalog and has no six-item limit.
- Selected is the ordered logical comparison set and may exceed six.
- Current Comparison Page is a derived six-image-at-most working set; it is not a
  duplicated persistent collection.
- Selected alone is not source-residency or preload authority.
- Statistics, Histogram, Line Profile, selection-derived Difference context,
  foreground loading, and generic source protection are bounded by the Current
  Comparison Page plus explicit correctness dependencies.
- P2 preload remains exactly one Folder Position ahead with max-one speculative
  worker; Comparison Page navigation creates no speculative preload.

## P4-A temporary curation — Complete

P4-A merged as PR #29 at the current baseline SHA.

`ReviewSelectionState` contains only captured ordered Selected IDs, temporary picked
native-source IDs, and internal active state. It owns no decoded source, preview,
cache, residency, worker, page copy, or derived Split/Difference document.

The product workflow is direct Pick in Multi View followed by **Keep Selection**.
The temporary Pick Set can span pages. Pick/Unpick/Clear do not change logical
Selected. Keep Selection filters the captured baseline in its original ordering and
then delegates to the existing Selected mutation path.

The Pick Set and baseline remain temporary and are **not persisted by P4-B**.

## P4-B Comparison Set Persistence — active implementation

P4-B introduces a versioned external JSON-based `.pixelscope` artifact with:

```text
kind = pixelscope-comparison-set
schema_version = 1
```

### Persisted v1 state

- ordered logical Selected native-source paths;
- optional Active source path;
- optional Primary source path;
- stable layout mode: `Auto`, `Single View`, or `Multi View`;
- validated RawProfile payload only when an already-resolved deterministic profile
  exists for that Selected RAW source.

Persistent identity is the normalized absolute local source path, not runtime
`document_id`.

### Explicitly not persisted

- Registered non-Selected catalog members;
- Current Comparison Page or `_page_start`;
- decoded `ImageDocument.source`, previews, gained previews;
- Difference cache or source residency/LRU/protection state;
- preload state, workers, load tokens, request/generation serials;
- P4-A Pick Set or captured baseline;
- Split/Difference derived documents;
- ROI, Line Profile selection, Saved ROI, Plots workspace state;
- Display Gain;
- window/dock/splitter geometry inside the Comparison Set;
- Recent history or diagnostics.

### Save semantics

Save Comparison Set uses current logical Selected in its current order. A temporary
P4-A Pick Set is not substituted. To save a curated subset the user first applies
**Keep Selection**, then saves the resulting logical Selected.

Save does not decode off-page sources, make Selected-wide sources resident, clear
P4-A temporary state, or alter Settings. Writes use a same-directory temporary file,
flush/fsync, then atomic replacement.

### Open semantics

Artifact parsing/schema validation occurs before workspace mutation. Existing
Registered catalog members are retained. For every loadable saved member:

```text
normal registration/reuse
        ↓
logical Selected in saved order
        ↓
Active position
        ↓
derived Current Comparison Page
        ↓
applicable Primary + stable layout
```

Saved members already Registered reuse their current runtime document identity.
Unregistered saved members use the existing registration path with RAW profile
resolution disabled at registration time. A saved resolved RAW profile is installed
before foreground selection; unresolved RAW remains pending and follows the existing
lazy foreground profile-resolution path.

Opening a Comparison Set changes logical Selected through the inherited
`_select_document_ids` boundary, so any captured P4-A curation state is invalidated
by the existing P4-A selection-mutation integration rather than by a new lifecycle.

Missing saved paths are skipped while preserving remaining saved order. A valid set
with zero loadable sources leaves current Registered/Selected/presentation unchanged.
Malformed JSON, wrong kind, invalid required fields, or unsupported schema version is
rejected before workspace mutation.

## Path/privacy boundary

Comparison Set v1 targets deterministic local workflows. It stores canonical
absolute local source paths. There is no fuzzy relocation, filename-only matching,
size-only matching, recursive moved-file search, or automatic repair.

Because `.pixelscope` files can contain local filesystem paths, users should treat
them as potentially sensitive metadata when sharing them.

## RAW/input baseline

Supported inputs remain `.png`, `.bmp`, `.jpg`, `.jpeg`, and `.raw`.

- Open Images/direct image D&D is selection-oriented.
- Open Folder/folder D&D is registration-oriented and preserves current selection.
- RAW sidecar/profile resolution follows the P3-D deterministic/lazy contract.
- No Profile Library/database, inference, demosaic, WB, CCM, or tone mapping is
  introduced by P4-B.

## Numerical/presentation baseline

Difference, RAW native/display semantics, Display Gain, Statistics, Histogram, Line
Profile, Split Channels, and pixel inspection keep their P3 contracts. Comparison
Set persistence adds no numerical transform and does not make Display Gain a
persistent setting.

Settings schema remains version 5. Comparison Set artifacts are separate from typed
ApplicationSettings and from workspace QSettings geometry/layout persistence.

## Active P4 sequence

1. P4-0 — P3 Closure & P4 Program Setup — Complete — PR #28
2. P4-A — Review Selection & Curation — Complete — PR #29
3. P4-B — Comparison Set Persistence — active implementation/validation
4. P4-C — Recent Entries & Comparison Set Entry UX — planned; do not begin runtime
   implementation until P4-B is merged
5. P4-D — Saved ROI & Analysis Workspace Productivity — planned
6. P4-E — Viewer Overlay & Export Productivity — planned
7. P4-F — Integration & Workflow Hardening — planned
