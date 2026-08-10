# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-10
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
| 4 | P3-D Unified Image Opening & RAW Profile Resolution | Input ownership + Current Comparison Page + deterministic RAW resolution | Active |
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

Status: Active on `feature/p3-d-unified-open` / PR #26.

### Authoritative hierarchy

P3-D uses this product/runtime model:

```text
Registered
    ↓ user selection
Selected                         # ordered logical set, may exceed 6
    ↓ Selected ordering + page offset
Current Comparison Page          # derived working set, max 6
    ↓ viewer representation
Presented                        # Multi=page, Single=one page-local slot
    ↓ native-source lifecycle
Resident when required
```

And:

```text
Analysis Working Set = Current Comparison Page
Viewer Slot = 1..6 within Current Comparison Page
```

Current Comparison Page is derived state, not a duplicated document collection.
Registration count and Selected count are not limited by viewer capacity.

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
- make those direct files the current ordered Selected set;
- Selected may exceed six without truncation;
- initial Current Comparison Page is the first six Selected images;
- ordinary and RAW share this entry;
- RAW uses deterministic profile resolution before direct-open registration;
- no separate **Open RAW with Profile...** action or `MainWindow.open_raw()` path;
- no `*.*` RAW wildcard.

### 2. Open Folder... — registration-oriented

Final folder command:

```text
Open Folder...    Ctrl+Shift+O
```

Requirements:

- use the native single-directory picker for File > Open Folder;
- keep multiple-folder registration through folder D&D / the registration API;
- use no custom multi-directory picker or Windows COM dependency;
- resolve/deduplicate multiple supplied directories deterministically;
- permit arbitrary practical registered folder count; do not cap at six;
- discover/register all supported immediate contents;
- do not change Selected, Current Comparison Page, presentation, or layout;
- do not auto-select a first image when selection is empty;
- do not create an implicit comparison group for two folders;
- skip folders with no supported images while continuing other folders;
- report compact registration status.

Registration-only folder input must preserve layout, active/primary document, ROI,
Line Profile selection, Difference presentation/cache, Display Gain, zoom/pan
preservation state, source residency, and existing worker/cache ownership where
applicable.

### 3. Drag/drop intent

```text
direct image files  -> register + select
folders             -> register only
```

- one/two/three/six/fifteen/etc. folders use one registration policy;
- exactly two folders have no special comparison behavior;
- multiple direct image files are all registered and Selected;
- mixed file + folder drop selects only explicitly dropped files;
- folder contents never overwrite/append implicit first-folder images to explicit
  direct-file selection.

### 4. Current Comparison Page authority

`MainWindow.current_comparison_documents()` or a semantic equivalent is the single
bounded working-set authority. Do not let subsystems independently use
`selected_documents[:6]` or unrelated `_page_start` slices.

The same Current Comparison Page must drive:

- Multi View;
- Single View page context;
- Statistics;
- Histogram;
- Line Profile;
- selection-derived Difference inputs;
- ROI/Line normalization;
- foreground page-load completion;
- current-page residency protection;
- local slot mapping.

Feature-owned explicit Difference pair/reference authority remains unchanged.

### 5. Large-selection navigation

For `Selected <= 6`:

```text
Current Comparison Page = Selected
```

Existing Auto/Single/Multi, primary, number-key, Left/Right, Folder Position,
ROI/Statistics/Histogram/Line Profile/Difference, residency, and preload behavior
must remain production-equivalent.

For `Selected > 6`:

- Current Comparison Page size is six except a short final page;
- Multi View uses the current page as its comparison workspace;
- large-selection Multi View keeps six-slot `Grid 3x2` geometry on every page;
- unused final-page slots are cleared;
- Single View presents one active page-local slot but keeps full current-page
  analysis/load context;
- viewer slots are always local `1..6`;
- number keys `1..6` address current-page local slots;
- Left/Right remains Previous/Next Selected Image across the complete ordered set;
- crossing a boundary updates Current Comparison Page automatically;
- Ctrl+Left/Ctrl+Right moves Previous/Next Comparison Page only while that
  direction is available; the application-wide shortcut is disabled at an endpoint;
- Comparison Page navigation does not wrap;
- the presentation-control row above the image workspace always exposes Page
  status, total Selected count, and current range; arrows remain visible and disable
  at unavailable endpoints;
- page movement preserves the active local slot where possible and clamps on a
  short final page;
- primary/focus changes are page-local and may not change Selected ordering/page
  membership.

PageUp/PageDown are never Comparison Page shortcuts.

### 6. Folder Position

For `Selected <= 6`, PageUp/PageDown retains existing Folder Position semantics and
P2 preload/promotion behavior.

For `Selected > 6`, Folder Position is unavailable. PageUp/PageDown is a no-op with
compact status; do not partially apply Folder Position to only Current Comparison
Page.

Other registered folders never participate automatically.

### 7. RAW profile resolution and foreground retry boundary

Direct RAW input preserves this sequence:

1. exact same-basename sidecar is parsed/validated if present;
2. current confirmation suppression and exact/minimum-size policy remain;
3. no sidecar opens editable RAW Profile entry;
4. invalid sidecar warns and opens editable fallback;
5. cancel prevents erroneous direct-open RAW registration;
6. multiple direct RAW files resolve independently;
7. existing-path reload retains document/profile identity.

Folder registration remains lazy:

```text
folder registration
    ↓
register pending RAW + deterministic sidecar path
    ↓
no profile dialog / no decode
    ↓
RAW enters foreground Current Comparison Page
    ↓
existing RAW profile resolver
    ↓
decode only after acceptance
```

Selected-but-off-page unresolved RAW must not prompt, decode, or require residency.
Unresolved RAW is excluded from speculative preload.

One foreground presentation attempt may prompt a given unresolved RAW at most once.
Cancel leaves it registered/pending, starts no worker, and passive rerenders must
not immediately re-prompt. A later explicit foreground intent may retry.

### 8. Source residency and preload

Preserve P2 exact native `source.nbytes` accounting and protected soft-budget LRU.
P3-D's large-selection refinement is:

- Selected membership alone is **not** a residency-protection owner;
- Current Comparison Page is protected;
- foreground loads, promoted preload, Difference dependencies, and other
  correctness-required owners remain protected;
- Selected-but-off-page sources may be evicted and normally reloaded when revisited.

Do not add Comparison Page preload. P2 preload remains exactly +1 Folder Position,
one group ahead, max-one preload worker.

### 9. Profile UI and exclusions

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
- Comparison Page preload system;
- broad MainWindow/Difference/P2 worker architecture rewrite;
- packaging/signing work.

### 10. P3-D test matrix

Focused automated coverage must establish:

#### Selected <=6 regression

- Current Comparison Page equals Selected;
- existing Auto/Single/Multi and number-key semantics remain unchanged;
- existing Folder Position behavior remains unchanged.

#### Selected >6

Use at least a 15-image canonical case:

- all 15 registered and logically Selected;
- page 1 = images 1–6;
- page 2 = images 7–12;
- final page = images 13–15;
- Previous reverses correctly and endpoints do not wrap;
- page movement does not change Selected membership/order;
- local slots remain 1–6;
- final-page stale tiles are cleared while six-slot geometry is retained.

#### Number keys / Single View / fine navigation

- number keys map to current-page local slots;
- image10 on page 7–12 is slot 4, not 10;
- Left/Right moves one Selected image;
- image12 → image13 crosses to page 13–15 and local slot 1;
- reverse crossing restores the previous page/slot;
- coarse page navigation preserves/clamps active local slot.

#### Analysis

After a page transition, Statistics/Histogram, Line Profile, Difference available
inputs, ROI normalization, and load-batch completion use the current page, not the
first six Selected images.

#### Residency

- current page is protected;
- Selected-but-off-page is not generically protected;
- Selected identity survives eviction/revisit;
- P2 budget/accounting semantics remain effective.

#### Navigation separation

- Ctrl+Left/Ctrl+Right is Comparison Page navigation;
- PageUp/PageDown remains Folder Position only;
- Selected>6 Folder Position is no-op;
- Selected<=6 Folder Position remains unchanged.

#### RAW

- off-page Selected unresolved RAW does not prompt/decode;
- entering foreground page resolves it;
- Cancel prompts once per foreground attempt;
- passive rerender does not immediately re-prompt;
- no worker starts after Cancel;
- a later explicit foreground action may retry.

#### Input regression

- Open Images multi-file, ordinary+RAW, six and >6;
- Open Folder plus multi-folder D&D 1/2/6/>6, dedup, registration-only, no first auto-select;
- folder/image/mixed D&D intents;
- registered-but-unselected state;
- folder-only runtime preservation.

## P3-E — Integration & Hardening

Close P3 over completed Difference/display/RAW/input semantics:

- cross-check native/normalized Difference and Display Gain independence;
- characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations;
- validate `Registered → Selected → Current Comparison Page → Presented → Resident`
  under large catalogs and page navigation;
- verify Selected<=6 production-equivalent behavior;
- exercise Folder Position, preload, eviction/reload, Difference cache, and Display
  Gain together;
- preserve P2 residency/preload/diagnostics contracts;
- complete Windows characterization and durable P3 documentation;
- do not add unrelated workflow/session or processed-RAW features during closure.

## Cross-phase invariants

P3 must preserve unless explicitly redesigned:

- Settings schema v5 migration/future-schema safety;
- exact native decoded-source residency accounting and protected soft-budget LRU;
- independent Difference Map Cache ownership;
- +1 one-position max-one Folder Position preload with foreground priority;
- exact RUNNING preload promotion without duplicate decode;
- advisory cancellation plus token/generation/request stale-result authority;
- observation-only sanitized **Help > Copy Diagnostics**;
- idempotent identical Statistics/Histogram requests;
- expensive I/O/numerics off the UI thread;
- explicit native source dtype/channel semantics and overflow-safe arithmetic;
- native source remains recoverable/authoritative when presentation transforms are
  active;
- input UX does not create a second RAW profile/decode authority;
- registration does not imply selection, page membership, presentation, decode, or
  residency.

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

Owner/local Windows validation passed on review baseline
`a462953b01c713a4cc4054a78854a0ed0fde9c4e`. The independent-review follow-up adds
shortcut-availability, cached six-source Difference parity, preload-separation tests,
and documentation changes after that baseline; owner/local Windows revalidation is
therefore pending for the current head.

Owner manual P3-D checks should include:

1. Open 15 images and verify 1–6 / 7–12 / 13–15 page ranges.
2. Verify local slot badges 1–6 on every page and empty final slots.
3. Verify Ctrl+Left/Ctrl+Right non-wrapping page navigation.
4. Verify Left/Right image12↔image13 boundary crossing in Single View.
5. Verify number key semantics on page 2.
6. Verify Statistics/Histogram/Line Profile move with Current Comparison Page.
7. Verify Selected>6 PageUp/PageDown does not perform Folder Position.
8. Reduce to A01/B01/C01 and verify PageDown → A02/B02/C02 as before.
9. Verify off-page folder RAW does not prompt; entering its page prompts once.
10. Cancel RAW profile and verify no immediate re-prompt/no worker; explicit retry
    may prompt again.
11. Exercise large-selection page visits under a small source-memory setting and
    verify off-page reload/eviction behavior.
12. Recheck native Open Folder and multi-folder D&D and folder/image/mixed D&D intent.
13. Recheck Difference, Display Gain, ROI, Split Channels, and Plots regressions.

## P3 exit criteria

P3 is complete when:

- P3-A Difference domain semantics remain stable;
- native samples remain authoritative and presentation cannot be confused with
  analysis processing;
- generic anchor-based Display Gain remains deterministic across RAW/ordinary
  presentation;
- unified input has one supported-extension contract;
- `Registered → Selected → Current Comparison Page → Presented → Resident` is
  explicit and regression-covered;
- Analysis Working Set equals Current Comparison Page;
- viewer slots are local 1–6 within the page;
- large Selected sets do not defeat P2 residency budget semantics;
- folder registration preserves active work and RAW folder registration avoids
  background/dialog side effects;
- RAW profile resolution remains deterministic across direct input, foreground
  page load, preload-after-resolution, reload, and existing-path identity;
- no speculative profile inference is introduced without evidence;
- P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs use the five-layer hierarchy consistently.

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
