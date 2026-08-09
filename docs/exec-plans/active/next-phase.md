# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
Current merged P3 baseline: P3-C / PR #25 merge commit
`7f6bef73e6712f6a14a4d401820a915196e25da2`

## Goal

Stabilize image-comparison, viewer-presentation, RAW-profile resolution, and input
semantics while keeping native decoded samples authoritative. Presentation and
input convenience must not silently redefine analysis domains, residency
ownership, or become an implicit RAW inference/processing pipeline.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Purpose | Status / prerequisite |
|---|---|---|---|
| 0 | P3-0 roadmap transition | Close/archive P2 and establish P3 | Complete — PR #21 |
| 1 | P3-A Difference domain extension | Gray + mixed-bit Difference semantics | Complete — PR #22 |
| 2 | P3-B RAW native/display semantics | Native RAW authority + generic gain core | Complete — PR #24 |
| 3 | P3-C Display Gain extension | Ordinary Gray/RGB/RGBA gain + RAW regression | Complete — PR #25 |
| 4 | P3-D Unified Image Opening & RAW Profile Resolution | Input ownership + deterministic RAW resolution | Active |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | After P3-D |

## Completed P3 foundation

### P3-A — Complete — PR #22

- Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, same-CFA Bayer ↔ Bayer.
- Equal effective depth uses native Difference; mixed depth independently
  normalizes to float32 `[0,1]`.
- `%FS` normalized threshold semantics and bounded quantile/memory policy.
- RAW Black/White, Display Gain, preview, and demosaic are outside Difference
  domain selection.

### P3-B — Complete — PR #24

- Native RAW source is authoritative.
- RAW 1× maps effective native full scale without subtracting Black or using White
  as display maximum.
- Generic float32 presentation core is
  `display = anchor + gain * (source - anchor)`.
- RAW gain >1 uses Black-derived anchors, including CFA-specific Bayer Black.
- No full-size Bayer Black map or full-frame float64 gain path.
- 1× is canonical-preview fast path; native analysis/residency/Difference remain
  independent of gain.

### P3-C — Complete — PR #25

Merged at `7f6bef73e6712f6a14a4d401820a915196e25da2`.

- one QApplication-session Display Gain state at 1×/2×/4×/8×/16×;
- ordinary Gray/RGB and RGB split channels use anchor 0;
- RGBA gains RGB only and preserves canonical alpha;
- RAW keeps P3-B semantics;
- Difference is excluded;
- 1× schedules no gained-preview worker;
- gain>1 uses resident source/shared numerical workers with stale-result rejection;
- gain is presentation-only and not persisted.

## P3-D — Unified Image Opening & RAW Profile Resolution

Status: Active on `feature/p3-d-unified-open`.

### Owner decision

The earlier speculative P3-D Profile Library/profile-suggestion scope is replaced
by a production input-policy requirement. The authoritative conceptual model is:

```text
Registered
    ↓ user selection
Selected
    ↓ viewer capacity / layout
Presented
    ↓ source lifecycle
Resident when required
```

Registration count is a Files/catalog concern. Selection is the user comparison
set. Presentation is bounded by current viewer layout. Resident is the independent
P2 decoded-native-source memory state. The existing six-tile viewer capacity must
never be reused as a folder/image registration limit.

### 1. Open Images... — selection-oriented

Final image-file command:

```text
Open Images...    Ctrl+O
```

Supported exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

Requirements:

- keep `QFileDialog.getOpenFileNames()` multi-file behavior;
- register every supported direct file;
- make those direct files the current selection;
- present according to existing viewer capacity;
- more than six supplied files remain registered/selected rather than being
  dropped/rejected at registration;
- ordinary and RAW share this entry;
- RAW uses deterministic profile resolution before direct-open registration;
- no separate **Open RAW with Profile...** action, RAW-only Empty Workspace button,
  RAW-only signal, or `MainWindow.open_raw()` path;
- no `*.*` RAW wildcard.

### 2. Open Folders... — registration-oriented

Final folder command:

```text
Open Folders...   Ctrl+Shift+O
```

Requirements:

- support multiple existing directories in one operation;
- use a maintainable Qt/PySide implementation without introducing a Windows COM
  dependency solely for this feature;
- resolve selected directories, deduplicate equivalent paths, and return them in
  deterministic order;
- permit arbitrary practical folder count; do not cap at six;
- discover/register all supported immediate contents;
- do **not** change current selection;
- do **not** change current presentation/layout;
- do not auto-select a first image when selection is empty;
- do not create an implicit comparison group for two folders;
- skip folders with no supported images while continuing other folders;
- report compact registration status such as
  `Registered N image(s) from M folder(s)` plus skipped-empty count where useful.

Registration-only folder input must preserve current comparison state including
layout, active/focus document, ROI, Line Profile selection, Difference
presentation/cache, Display Gain, zoom/pan preservation state, source residency,
and existing worker/cache ownership where applicable.

### 3. Drag/drop intent

Folder and image D&D must match the corresponding menu intent:

```text
direct image files  -> register + select/present
folders             -> register only
```

Requirements:

- one/two/three/six/fifteen/etc. folders use one registration policy;
- remove the exactly-two-folder auto-comparison special case;
- multiple direct image files are all registered and selected;
- direct image registration is not capped at six;
- mixed file + folder drop registers everything supported but selects only the
  explicitly dropped direct files;
- folder registration must not overwrite or append implicit first-folder images
  to explicit direct-file selection.

### 4. Registration/selection/presentation ownership

`io.path_discovery` owns the extension/filter contract. `.json` remains metadata
only and never appears as a standalone image document.

`ImageInput` remains the discovery identity. P3-D should keep responsibilities
semantically equivalent to:

```text
register inputs/folders
select documents
present selection
```

`_register_inputs()` must not own selection or layout changes. Callers with
selection intent explicitly invoke selection afterward. Folder registration never
invokes the presentation lifecycle.

A valid state with `documents > 0` and zero selected documents is required. The
central workspace uses the existing EmptyWorkspace component in two modes:

- truly empty → **Drop images or folders here** + Open Images/Open Folders;
- registered but unselected → **Select an image from Files to view**.

### 5. Folder Position

PageUp/PageDown derives only from currently selected comparison documents. It
continues to support one-to-six selected files from distinct folders and preserves
existing P1/P2 atomic endpoint/preload/promotion semantics. Other registered
folders do not join the active Folder Position merely because they exist in Files.

### 6. RAW profile resolution

Direct RAW input preserves this sequence:

1. exact same-basename sidecar, if present, is parsed/validated;
2. current confirmation suppression and exact/minimum-size policy remain in force;
3. no sidecar opens editable RAW Profile entry;
4. invalid sidecar warns and opens editable fallback;
5. cancel prevents erroneous direct-open RAW registration;
6. multiple direct RAW files resolve independently;
7. existing-path reload retains document/profile identity.

Folder registration must not generate a dialog storm. P3-D uses a small lazy
boundary rather than broad P2 redesign:

```text
folder registration
    ↓
register pending RAW path + deterministic sidecar path
    ↓
no profile dialog / no decode
    ↓
foreground selection/load requires source
    ↓
existing RAW profile resolver
    ↓
decode only after profile acceptance
```

Unresolved RAW without a resolved profile is excluded from speculative preload.
This avoids dialogs from speculative/background work and does not guess profiles
from file size or weak evidence.

Existing RawProfile migration, packed/unpacked validation, effective bit depth,
stride/offset/endian/alignment, Bayer pattern, Black/White metadata, exact-size
policy, same-path reload, preload identity after profile resolution, and source
residency semantics remain authoritative.

### 7. Profile UI and exclusions

User-facing profile buttons are **Load Profile...** / **Save Profile...**. JSON
remains the storage format.

P3-D adds no:

- global Profile Library/database;
- Settings-owned profile collection;
- profile CRUD/favorites/search;
- last-profile reuse or apply-to-all UI;
- size-only/fuzzy suggestion;
- sensor/Bayer inference;
- automatic Black/White estimation;
- profile schema version field without migration need;
- demosaic, white balance, CCM, tone mapping;
- new Difference mode or Display Gain redesign;
- session persistence or Recent Files/Folders;
- Settings schema bump;
- source-residency/preload worker-policy redesign;
- broad MainWindow rewrite;
- packaging/signing work.

### 8. P3-D test matrix

Focused automated coverage must establish:

#### Open Images

- multi-file selection;
- all supported direct files registered;
- direct files become active selection;
- ordinary + RAW mixed direct selection;
- six and greater-than-six supplied images do not cause registration loss;
- viewer presentation remains bounded by existing capacity.

#### Open Folders

- multi-directory selection;
- 1, 2, 6, and >6 folder registration;
- deterministic duplicate-folder deduplication;
- current selection unchanged;
- current viewer/layout unchanged;
- no first-image auto-selection;
- no implicit comparison group;
- empty/no-supported-image folder skip/reporting.

#### Folder D&D

- one, two, 3–6, and >6 folders are registration-only;
- no exactly-two-folder special case;
- current selection/presentation preserved.

#### Image D&D

- one and multiple files register + select;
- six and >6 direct files are all registered;
- presentation remains bounded by existing viewer contract.

#### Mixed D&D

- direct files and folder contents are all registered;
- only explicit direct files become the selection;
- folder contents are not implicitly selected.

#### Registered but unselected

- registered documents + zero selection is stable;
- central workspace prompts selection from Files;
- no load/render crash;
- selection-dependent actions remain unavailable.

#### RAW folder registration

- no registration-time profile dialog for pending folder RAW;
- deterministic sidecar path is retained;
- profile resolves at actual foreground load;
- unresolved RAW does not start speculative preload;
- no automatic profile inference.

#### Folder Position and runtime preservation

- many registered folders do not participate automatically;
- only selected folders advance;
- PageUp/PageDown regression remains correct;
- folder-only registration does not reset ROI/Line Profile/Difference/Display Gain,
  change layout/active/focus, trigger unrelated decode, invalidate Difference
  cache, or alter source-residency ownership.

Existing regression suites remain authoritative for RAW decode/profile exact-size,
preload/promotion/reload identity, source residency, Difference, Display Gain,
Statistics/Histogram/Line Profile, and Split Channels.

## P3-E — Integration & Hardening

Close P3 over the completed Difference/display/RAW/input semantics:

- cross-check native/normalized Difference and Display Gain independence;
- characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations;
- validate Registered/Selected/Presented/Resident behavior under large catalogs;
- preserve P2 residency/preload/diagnostics contracts;
- verify unified input/profile resolution through navigation, preload, reload, and
  existing-path identity;
- complete Windows characterization and durable P3 documentation;
- do not add unrelated workflow/session or processed-RAW features during closure.

## Cross-phase invariants

P3 must preserve unless explicitly redesigned:

- Settings schema v5 migration/future-schema safety;
- exact native decoded-source residency accounting and protected soft-budget LRU;
- independent Difference Map Cache ownership;
- +1 one-position max-one preload with foreground priority;
- exact RUNNING preload promotion without duplicate decode;
- advisory cancellation plus token/generation/request stale-result authority;
- observation-only sanitized **Help > Copy Diagnostics**;
- idempotent identical Statistics/Histogram requests;
- expensive I/O/numerics off the UI thread;
- explicit native source dtype/channel semantics and overflow-safe arithmetic;
- native source remains recoverable/authoritative when presentation transforms are
  active;
- input UX does not create a second RAW profile/decode authority;
- registration does not imply selection, presentation, decode, or residency.

## Validation policy

For P3-D, the Chat implementation agent writes tests but does not bootstrap/run a
local virtual environment. The repository owner runs the Windows `.venv` contract:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Do not claim PASS without observed output.

Tests were not run by this Chat implementation agent. Owner/local Windows
validation is pending.

Owner manual P3-D checks should include:

1. Open Images with PNG/JPEG/BMP and multi-file selection.
2. Open Images with more than six files: all registered, presentation bounded.
3. RAW + valid sidecar and RAW without sidecar.
4. Invalid RAW sidecar warning/edit flow and cancel behavior.
5. Open Folders with 1, 2, 6, and >6 folders.
6. Folder registration while an existing comparison/ROI/Line/Difference is active.
7. No automatic first-image selection after folder registration.
8. Registered-but-unselected center prompt.
9. Folder D&D for 1, 2, 6, and >6 folders with unchanged selection.
10. Direct image D&D and mixed file + folder D&D.
11. Folder RAW registration without dialog storm, then selection-time resolution.
12. PageUp/PageDown using only currently selected folders among a larger catalog.
13. RAW/ordinary Display Gain and Statistics/Difference/Histogram/Line Profile/
    Split Channels regressions.

## P3 exit criteria

P3 is complete when:

- P3-A Difference domain semantics remain stable;
- native samples remain authoritative and presentation cannot be confused with
  analysis processing;
- generic anchor-based Display Gain remains deterministic across RAW/ordinary
  presentation;
- RAW Black-anchored and ordinary zero-anchored gain remain regression-covered;
- unified input has one supported-extension contract;
- registration/selection/presentation/residency ownership is explicit and no
  six-item registration cap leaks from viewer geometry;
- folder registration preserves active work and RAW folder registration avoids
  background/dialog side effects;
- RAW profile resolution remains deterministic across direct input, foreground
  load, preload-after-resolution, reload, and existing-path identity;
- no speculative profile inference is introduced without evidence;
- P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs use Registered/Selected/Presented/Resident terminology consistently.

Demosaic is not required for P3 completion under the current owner decision.

## Later roadmap after P3

- **P4 — Workflow & Session Productivity:** persistent comparison sessions,
  Recent Files/Folders, saved ROI manager, arbitrary-angle line sampling, alpha
  overlay, and productivity/export workflows.
- **P5 — Remote IQA Platform:** remote submission/results, server/job API, GPU
  worker, artifact/heatmap/result comparison.
- **P6 — Identity, Access & Remote Operations:** login/SSO, token lifecycle,
  permissions, and operational administration.
- **P7 — Release Engineering & Distribution:** PyInstaller 5.7 `onedir`, portable
  ZIP, Inno Setup, clean-PC smoke, signing, updater/release process.
