# PixelScope user guide

## Register, select, and view images

PixelScope distinguishes five states:

- **Registered**: known to Files.
- **Selected**: ordered logical comparison membership.
- **Current Comparison Page**: current maximum-six working subset of Selected.
- **Presented**: current viewer representation.
- **Resident**: decoded native source currently retained when required.

The six-image limit belongs to Current Comparison Page, not Files or Selected.
`Analysis Working Set = Current Comparison Page`.

### Open Images

Use **File > Open Images...** (`Ctrl+O`) to choose images you want to compare now.
Supported formats are:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

All supported chosen files are registered and become the ordered Selected set. More than
six are shown in six-image Comparison Pages.

### Open Folder

Use **File > Open Folder...** (`Ctrl+Shift+O`) to register a dataset folder. Opening a
folder adds supported files to Files but does not automatically change the current
Selected/current page/view merely because a new folder was registered.

To register several folders, drag/drop them into Files. There is no special two-folder
auto-comparison behavior.

### RAW

RAW uses the same Open Images command. PixelScope may use a same-basename JSON profile or
ask for RAW dimensions/packing/CFA metadata. Folder-registered unresolved RAW can remain
pending until it becomes a foreground current-page source.

RAW native pixels remain analysis authority. Display Gain changes presentation only.

## Navigate large Selected sets

The presentation row shows current page/range.

- **Left / Right**: previous/next Selected image.
- **Ctrl+Left / Ctrl+Right**: previous/next Comparison Page when available.
- **1..6**: current page-local viewer slots.
- **PageUp / PageDown**: Folder Position workflow, not Comparison Page navigation.

Primary is local to the current page and does not reorder logical Selected.

## Display Gain

Display Gain choices are 1×/2×/4×/8×/16×.

- 1× reuses canonical preview.
- Ordinary Gray/RGB gain is anchored at zero.
- RAW gain >1 is anchored at Black Level.
- Difference uses its own Difference Gain and is not affected by general Display Gain.

Statistics, Histogram, Line Profile, Split data, and Difference consume native source,
not gained preview pixels.

## Difference

Choose Difference inputs and use **Calculate** to establish a Difference result.

Supported comparison families are:

- Gray ↔ Gray;
- RGB/RGBA ↔ RGB/RGBA;
- compatible same-CFA Bayer ↔ Bayer.

Equal effective bit depth uses native code-domain Difference. Mixed depth uses normalized
full-scale Difference. After Calculate succeeds, toolbar Diff hides/shows that active
result; it does not silently infer or recalculate another pair.

## Review and Keep Selection

Eligible native Multi View tiles provide **Pick**. Pick is temporary and independent from
Active and Primary.

- **Selected N**: number of temporary Picks.
- **Clear Selection**: clear Picks only.
- **Keep Selection**: replace logical Selected with the picked subset in original Selected
  order.

Pick state is not saved. Keep Selection also clears any active Difference binding before
the Selected change; it does not purge valid Difference cache entries.

## Sessions and local Recent

Use **File > Save Session** / **Open Session** for durable local workspace intent. Session
v1 does not save runtime source arrays, caches, workers, temporary Picks, running Remote
IQA jobs, or IQA historical state.

File menu also provides:

- Open Recent Images;
- Open Recent Folders;
- Open Recent Sessions.

These are separate from **Open Recent IQA Results**.

# Remote IQA

Remote IQA connects PixelScope to an external GPU IQA service while keeping the local
workspace independent.

```text
Setup / submit
    ↓
Jobs
    ↓ explicit Open Result
Results
    ↓ optional Inspect in Viewer
native local inspection
```

Tracking jobs or browsing Results does not change Files/Selected/current page. Only an
explicit successful **Inspect in Viewer** enters the local source/viewer workflow.

## Configure Remote IQA

Open **Edit > Settings... > Remote IQA**.

Configure:

- **Server base URL**;
- shared-storage mappings:
  - **Root ID**: portable logical identifier;
  - **Client path**: drive/UNC path on this machine;
- optional **Staging root**.

Example:

```text
Root ID: iqadata
client path: G:\IQA
server path: /home/data/IQA
```

PixelScope sends/stores the portable Root ID + relative path. The client path is
machine-local and may differ across workstations.

## Submit Current Pair

In IQA **Setup**, Current Pair submits exactly two variants A/B.

Requirements:

- exactly two underlying Current Comparison Page sources;
- PNG/JPG/JPEG/BMP;
- matching dimensions.

RAW is not silently converted for Remote IQA.

A/B identity is independent from Primary, Active, view reorder, Single/Multi View,
Display Gain, Difference, and Split presentation.

## Submit Folder Pair

1. Choose Folder A and Folder B.
2. Click **Validate / Preview**.
3. Review pair count/order.
4. Click **Submit Folder Pair**.

Rules:

- immediate files only;
- no recursive scan;
- symlinks excluded;
- PNG/JPG/JPEG/BMP only;
- deterministic Unicode-NFC lexical order;
- equal non-zero eligible counts;
- pair-by-index;
- each pair has matching dimensions;
- maximum 512 Scenes.

Folder Pair preparation does not register/select/decode the whole remote batch into the
local workspace.

## Jobs

Use the IQA **Jobs** tab while work runs remotely. PixelScope remains usable.

Typical states include:

```text
queued
preparing
extracting
aggregating
writing
succeeded
partial
failed
cancelled
```

### Cancel

**Cancel** requests server cancellation for a non-terminal job. The server owns final
state.

### Open Result

A succeeded/partial job never automatically replaces the current Result. **Open Result**
is explicit and becomes useful after PixelScope obtains and resolves the published
logical Result reference.

Temporary result-reference GET failures may use bounded retry. Job creation itself is not
blindly retried because timeout may happen after server acceptance.

## Open an IQA Result directly

Use **File > Open IQA Result...** to choose an already-published Result directory.

File open and Jobs Open Result use the same canonical Results workspace. Current schema
v2 opens summary-first: PixelScope reads the manifest/summary and initially shows
**Absolute measurements** without scanning every Scene grid.

The IQA **Reference** control is independent from image Primary. Selecting a Reference may
prepare required Scene grids in the background. If deferred grid work fails, PixelScope
returns to the last valid Result presentation rather than leaving controls/plots with
mismatched semantics.

## Explore Results

The Results workspace provides:

- Dataset Overview;
- attribute/Scene hierarchy;
- Scene Trend;
- source identity cards;
- COMPLETE/PARTIAL diagnostics;
- P5-D Inspect/Return/spatial controls;
- P5-E Provenance.

For schema v2, Absolute mode shows source-oriented measurements. Relative mode derives
selected target/reference comparisons locally using the canonical schema-v2 math.

Schema v1 remains explicit **historical / read-only** compatibility.

## PARTIAL Results

A PARTIAL Result contains fully published successful Scenes plus failed/cancelled
requested-Scene diagnostics.

Successful Scenes remain normally browseable. Failed/cancelled outcomes are not turned
into fake successful Scenes. A zero-success job is failed/cancelled rather than PARTIAL;
an all-success job is COMPLETE.

# Historical Remote IQA Results — P5-E

P5-E adds history around the same canonical Result loader. It does **not** rerun IQA or
create a second Result parser.

## Open Recent IQA Results

Use **File > Open Recent IQA Results**.

The menu retains at most 10 successful historical Result opens in MRU order. Opening the
same historical locator moves it to the front instead of duplicating it.

History is updated after successful opens from:

- File > Open IQA Result...;
- Jobs > Open Result;
- Open Recent IQA Results itself.

Failed, unsupported, corrupt, or historical-identity-mismatch opens are not recorded as a
new successful history item.

Use **Clear Recent IQA Results** to clear only IQA history. Recent Images/Folders/Sessions
remain unchanged.

## Portable logical history vs local history

For production/shared-storage Results, a Recent entry stores:

```text
storage_root_id + relative_path
```

It does **not** store the current mapped drive/UNC path as portable identity. Each reopen
uses the current Remote IQA mapping for that Root ID.

This means a Result can be recorded on one mapping and reopened after the same Root ID is
mapped to another valid client path.

A manual Result outside configured roots, and schema-v1 history, may use a machine-local
absolute path. Such entries are not portable between different filesystem layouts.

## Missing or offline historical Result

If a Recent logical/local location is unavailable, PixelScope warns that the historical
Result cannot currently be opened and offers **Remove** or **Keep**.

Choose **Keep** if the storage is temporarily offline or will be remapped/restored.
Choose **Remove** only when you want to delete that entry from Recent history.

An unavailable entry is not silently deleted.

## Result replacement / identity mismatch

A Recent entry remembers the observed:

```text
result_id + schema_version
```

When reopened, PixelScope first lets the canonical reader validate the artifact. Before
the newly read Result replaces the current Results presentation, P5-E verifies that its
identity still matches the historical entry.

If the same path/root now contains a different Result identity:

- the reopen is rejected;
- the previous valid Result remains displayed;
- the old Recent entry remains unless you explicitly Remove it.

PixelScope does not add a second whole-Result hash for this purpose; the existing Result
reader remains structural/numerical integrity authority.

## Result-only mode when original images are unavailable

A valid server Result remains useful even when original source images are offline,
missing, unmapped, changed, or did not publish a portable source locator.

Opening/reopening the Result does **not** hash/decode all source images. You can still use:

- Dataset Overview;
- Absolute/Relative hierarchy;
- Scene Trend;
- PARTIAL diagnostics;
- Provenance.

Only explicit **Inspect in Viewer** requires native source verification.

If native verification later fails, that means native inspection is unavailable/failed;
it does not retroactively make the already-valid Result corrupt.

## Provenance

Open the **Provenance** page inside Results.

For schema v2 it shows published metadata such as:

- Result ID;
- schema version;
- COMPLETE/PARTIAL state;
- historical locator;
- selected Scene `measurement_context_id`;
- representative/preprocessing/model/weighting/geometry provenance IDs;
- each variant/source ID;
- source Root ID when published;
- source relative path;
- source SHA-256;
- width/height;
- current local native-inspection status.

Provenance is passive metadata display. It does not open source pixels and does not
recompute IQA.

For schema v1, Provenance explicitly says historical/read-only and only shows metadata
that actually exists in v1. It does not invent schema-v2 measurement-context/root fields.

# Inspect an IQA Scene in Viewer

For a selected schema-v2 Scene, **Inspect in Viewer** is the explicit transition into the
normal PixelScope viewer.

Inspect requires all necessary unique source bindings to resolve and verify. PixelScope
checks current logical-root mapping, containment, ordinary-image eligibility, published
dimensions, exact encoded-byte SHA-256, and decode before local mutation.

Verification is all-or-nothing. Missing/moved/remapped/hash/dimension/decode problems do
not partially select a Scene.

When successful, verified sources are committed to the existing Files/native-source
owner and then shown through the normal Selected/current-page viewers. If a path was
already Registered with stale resident pixels, the verified published generation replaces
that stale generation rather than silently reusing old bytes.

Repeated variant bindings may share one concrete source. PixelScope uses one canonical
local source/document while keeping the IQA variant aliases in Results/spatial inspection.

## Spatial inspection

Choose a **Spatial attribute** after successful Inspect. PixelScope loads the selected
Scene grid as needed and shows a vector/block overlay in the normal viewer.

Block Inspector exposes cell validity, W/S1/S2/count, mean, optional Reference-relative
value, and mapped source geometry. Invalid/pair-invalid cells remain invalid rather than
being presented as zero.

IQA Reference and local Primary remain independent.

## Return

The first successful Inspect captures one transient pre-Inspect local workspace target.
Use **Return** to restore it if no newer conflicting local intent occurred.

Newer Selected/Files/layout/Primary/Pick intent invalidates Return instead of being
overwritten. A new Pick is preserved; PixelScope does not clear newer curation just to
restore an older snapshot.

Opening another Result from File, Jobs, or Recent first tears down old Inspect/spatial
work so stale Scene callbacks cannot overwrite the new Result/workspace.

# Session boundary

Session v1 does not store Remote IQA Result/history state. Closing and reopening a Session
does not restore:

- running Remote IQA jobs;
- IQA Result locator/identity;
- IQA Reference;
- selected IQA Scene;
- Provenance selection;
- Inspect/Return state.

Recent IQA Results is separate observer metadata and survives normal window close/recreate
through QSettings, independently from Session.

# Remote IQA debug tools

When `PIXELSCOPE_REMOTE_IQA_DEBUG=1`, developer-only tools may appear for request/replay/
localhost contract validation. They are not production-server architecture and do not
perform GPU IQA computation.

# Workspace reset and closing

The IQA dock follows Plots-style Float/Dock, Maximize/Restore, Hide, and workspace reset
behavior.

Closing PixelScope cancels feature-local client workers/resolvers but does not cancel
durable server jobs merely because the desktop application closed.

# Current P5-E status

P5-D is merged in current main. P5-E is Active in Draft PR #44. Owner Windows manual
validation A–G is listed in
[`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md) and remains required before
P5-E merge.
