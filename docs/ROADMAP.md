# Roadmap

## Delivered baseline

### P0/P1 product foundation

- PNG/BMP/JPEG and profile-described RAW loading with native source preservation.
- Files workspace, ordered selection, synchronized cursor/range/ROI/line state,
  Folder Position navigation, and fixed one-to-six-image presentation layouts.
- Statistics, Histogram, Line Profile, Difference, Split Channels, structured
  status, and persisted workspace/Plots state.
- RAW10/12/14 plus unpacked uint8/uint16 decoding with deterministic fixtures.
- P1-D/P1-E/P1-F workspace-polish program completed as PR #10–#12.
- Historical P1 plan:
  `docs/exec-plans/completed/p1-d-to-p1-f-workspace-polish.md`.

### P2 — Runtime Foundation, Settings & Performance — Complete

Completed sequence:

`P2-0 → P2-A1 → P2-A2 → P2-B → P2-C → P2-D → P2-E → P2-F`

- P2-0 merged as PR #13.
- P2-A1 identity/resources merged as PR #14.
- P2-A2 typed settings/runtime integration merged as PR #15.
- P2-B byte-budgeted decoded-source residency merged as PR #16.
- P2-C bounded next-position preload merged as PR #17.
- P2-D deterministic runtime diagnostics merged as PR #18.
- P2-E RUNNING preload foreground reuse merged as PR #19.
- P2-F performance characterization/hardening merged as PR #20 at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.

P2 closes with settings schema v5, independent source/Difference memory budgets,
protected soft-budget source residency, +1 one-position max-one preload, RUNNING
preload authority promotion, deterministic sanitized diagnostics, and
hardware-independent correctness/resource/lifecycle merge gates.

Historical P2 plan:
`docs/exec-plans/completed/p2-runtime-foundation-settings-performance.md`.

## Revised forward sequence

`P3 Image Semantics & RAW Processing`
→ `P4 Workflow & Session Productivity`
→ `P5 Remote IQA Platform`
→ `P6 Identity, Access & Remote Operations`
→ `P7 Release Engineering & Distribution`

Image-analysis and RAW/input semantics are stabilized before persistent sessions
or remote/release layers are built around them.

## P3 — Image Semantics & RAW Processing — Complete

P3-0 merged as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`. P3 roadmap replanning merged as
PR #23 at `4c7d1bbbb4476134f76a204578098d35a03feca2`.

### P3-A — Difference Gray / Mixed Bit-Depth Support — Complete

Merged as PR #22 at `769588bf869847da844cfc0b77c008023d8b048b`.

Delivered:

- Gray ↔ Gray, RGB/RGBA ↔ RGB/RGBA, and same-CFA Bayer ↔ Bayer;
- explicit rejection of cross-family/size/CFA mismatch;
- native code-domain Difference for equal effective bit depth;
- independently normalized float32 `[0,1]` Difference for mixed effective depth;
- `%FS` normalized threshold semantics;
- bounded mixed-bit metrics/quantiles and cache domain metadata;
- RAW Black/White and display transforms excluded from Difference normalization.

### P3-B — RAW Native & Display Semantics — Complete

Merged as PR #24 at `1817490a08c61da9087efe9c3c6afd8bd85838f0`.

Delivered:

- native decoded RAW remains authoritative source;
- 1× RAW display maps effective native full scale without subtracting Black or
  using White as display maximum;
- generic float32 anchor-based display core:
  `display = anchor + gain * (source - anchor)`;
- RAW gain >1 uses Black-derived anchors, including per-CFA Bayer Black levels;
- no full-frame Bayer Black map and no full-frame float64 gain math;
- 1× canonical-preview fast path, async viewer-local gain>1 path, stale-result
  rejection, and hidden-view derived-buffer release;
- native analysis/residency/Difference semantics remain independent of gain.

### P3-C — Display Gain Extension — Complete

Merged as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

Delivered:

- one application-session Display Gain state/control at 1×/2×/4×/8×/16×;
- ordinary Gray/RGB and RGB split channels use anchor 0;
- RGBA gains RGB only and preserves canonical alpha;
- RAW keeps P3-B 1× and Black-anchored gain semantics;
- Difference remains excluded from general Display Gain;
- 1× remains no-work canonical-preview reuse;
- gain>1 uses resident source and shared numerical workers with stale rejection;
- Display Gain remains presentation-only and is not persisted.

### P3-D — Unified Image Opening & RAW Profile Resolution — Complete

Merged as PR #26 at
`b16ecc558ac24225e9ddfddfca4e48e37fde61ca`.

P3-D establishes the authoritative runtime hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset
Current Comparison Page        # max 6
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.
Viewer slots are local `1..6` inside the Current Comparison Page; global Selected
ordinal and viewer slot are separate concepts. Registration and logical selection
are not constrained by six. The six-image boundary belongs to the Current
Comparison Page working set.

Delivered input/page/runtime policy:

- **Open Images...** is selection-oriented and preserves arbitrary practical
  multi-file selection; the first six become the initial Current Comparison Page.
- **Open Folder...** and folder drag/drop are registration-oriented and do not
  change Selected or presentation state.
- direct image-file drag/drop registers and selects only the explicitly dropped
  files; mixed drops keep folder registration separate from direct-file selection.
- registered-but-unselected is a valid workspace state.
- `Selected <= 6` keeps prior Auto/Single/Multi behavior; `Selected > 6` is derived
  into ordered six-image pages without changing Selected membership/order.
- Ctrl+Left/Ctrl+Right is non-wrapping Comparison Page navigation; Left/Right remains
  fine Selected-image navigation; PageUp/PageDown remains Folder Position only.
- Statistics, Histogram, Line Profile, selection-derived Difference context,
  ROI/Line normalization, current-page foreground loading, residency protection,
  and local slot mapping share one Current Comparison Page authority.
- Selected alone is not a residency owner. Off-page Selected sources may be evicted
  and normally reloaded on revisit.
- Folder-registered unresolved RAW remains pending off-page; profile resolution is
  lazy at foreground page entry, Cancel suppresses passive immediate re-prompt,
  and later explicit foreground intent may retry.
- P2 preload remains exactly +1 Folder Position with max-one speculative worker;
  no Comparison Page preload was introduced.

P3-D did not add Profile Library/database, inference, demosaic, white balance, CCM,
tone mapping, a new Difference mode, settings schema changes, or residency/preload
redesign.

### P3-E — Integration, Presentation UI Polish & Phase Hardening — Complete

Merged as PR #27 at
`835634a58609601605fd0fc18a3028b64225f535`, completing P3.

P3-E added no new image-analysis semantics. It hardened the merged P3 production
contract:

- preserved native source authority across Difference, RAW presentation, Display
  Gain, Statistics, Histogram, Line Profile, Split Channels, and residency;
- preserved same-bit native and mixed-bit normalized Difference independence from
  Display Gain and RAW Black/White/display presentation;
- preserved 1× canonical-preview fast paths and gain>1 float32/Black-anchored paths
  without source/generation/residency mutation;
- hardened `Registered → Selected → Current Comparison Page → Presented → Resident`
  ownership for large selections without Selected-wide eager decode/protection;
- preserved <=6 Folder Position/preload behavior and kept Comparison Page
  navigation independent from speculative preload;
- preserved lazy RAW profile resolution, Split Channels transient presentation,
  Difference pair/cache ownership, and P2 analysis-request dedup contracts;
- finalized the Presentation Control Row with stable icon-backed page `QToolButton`s,
  accessibility, fixed page/range labels, shared design tokens, and unchanged
  keyboard ownership;
- added production-composition regression coverage for actual page-button clicks,
  Display Gain focus/shortcut ownership, and Qt teardown/recreation.

Independent review's initial production-composition integration-test blocker was
resolved by follow-up work. The repository owner reported a **full local Windows
pytest PASS** on code/test head
`1af4f6703656028ca7d0e2bdaf369cce029e4bb1`; the later
`b29963cbf91bf5c022a53d9562e36510e80112a2` commit changed only
`docs/AGENT_HARNESS_NOTES.md` before the final merge.

No unobserved Ruff, Ruff-format, mypy, pip-check, docs-check, or `git diff --check`
PASS is inferred from that closure evidence.

Historical P3 plan:
[`docs/exec-plans/completed/p3-image-semantics-raw-input.md`](exec-plans/completed/p3-image-semantics-raw-input.md).

The initial P3 Profile Library/demosaic direction was intentionally replaced or
deferred, not delivered. P3 does not include demosaic, white balance, CCM, tone
mapping, Profile Library/database, profile CRUD/favorites/search, fuzzy/size-only
profile suggestion, sensor/Bayer inference, or automatic Black/White estimation.

## P4 — Workflow & Session Productivity — Active

P4-0 merged as PR #28 at
`e30c49d6759715228a820d673ad8939ea9a3afe8`.
P4-A Review Selection & Curation merged as PR #29 at
`3486146494076e9b513843b90ec44e504043729e`.
P4-B Comparison Set Persistence merged as PR #30 at
`3a19589e6cbad5fa8c814c522df6a553f59ee340`.
PR #32 runtime stabilization merged at
`e1ccf264f86e37b438c923faceae96c3ecb539b7`, and PR #33 Difference/source-curation
semantics merged at `51a540c92c372d71e02fd849fb5e0d406d0e9327`.
P4-C Session persistence / typed Recent is implemented and owner-validated on
PR #31, pending merge closure.

Active plan:
[`docs/exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Recommended sequence:

`P4-0 → P4-A → P4-B → P4-C → P4-D → P4-E → P4-F`

### P4-0 — P3 Closure & P4 Program Setup — Complete

Merged as PR #28. This docs-only transition closed P3 status, archived the P3 plan,
and established the P4 execution sequence without adding runtime/UI behavior.

### P4-A — Review Selection & Curation — Complete

Merged as PR #29. P4-A adds temporary review/curation state without changing the
P2/P3 numerical or resource-ownership contracts.

Implemented workflow:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
direct temporary Pick Set
    ↓ Keep Selection
new Selected subset
```

There is **no explicit Review Select mode**. Eligible native source tiles in Multi
View expose a stable **Pick** control directly. The first checked Pick captures the
current ordered Selected IDs as the temporary baseline internally. Checked Pick
membership is shown by the depressed button state plus a high-contrast bright-yellow
tile-wide border; Active and Primary retain independent meanings. Picks persist
across Comparison Pages and may remain off-page without becoming residency or
protection owners.

The presentation row exposes the curation state directly as
`Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
Here `Selected N` is the temporary Pick Set count, not Files logical Selected count.
**Clear Selection** clears only temporary picks. **Keep Selection** is disabled at
zero picks and is the only curation operation that changes logical Selected. It
filters the captured baseline Selected ordering by picked membership, so pick order
cannot reorder the result. Non-picked images remain Registered. There is no
user-facing Cancel command.

A different logical Selected-membership mutation, including Files context-menu
removal, invalidates the captured temporary baseline/Pick Set before or with the
normal mutation. Registration-only folder input preserves curation state because it
does not change Selected.

Pick membership does not own or trigger decode, `_ensure_loaded()`, source
residency/protection/LRU touch, preload, foreground promotion, Display Gain preview
generation, numerical analysis, Difference calculation, or Difference cache
identity. Split/Difference derived documents are not independent pick identities.
Temporary curation state is not persisted and Settings schema remains v5.

Focused coverage includes state lifetime/idempotence/order, direct first-Pick
baseline capture, stable Pick checked state, Active/Primary/Pick separation,
tile-wide yellow persistence, `1/2/6/7/15/50` Selected cases, cross-page picks,
zero-pick safety, baseline-order Keep Selection, production Files-removal
invalidation, viewer pan/ROI/Line drag non-pick behavior, post-Keep Files
selection/first-Active state, derived-presentation identity rejection, external
Selected mutation invalidation, and 50-image bounded load/protection/preload
regression.

### P4-B — Comparison Set Persistence — Complete

Merged as PR #30 at `3a19589e6cbad5fa8c814c522df6a553f59ee340`.
P4-B established the first external `.pixelscope` v1 **Comparison Set** artifact.
That artifact remains a historical compatibility format and is still read-compatible
under P4-C Session v1.

Comparison Set v1 persists ordered logical Selected native-source references,
optional Active, optional applicable Primary, stable layout mode, and minimum resolved
RAW metadata needed to reconstruct a RAW source. Persistent source identity is a
normalized **absolute local path** and v1 performs no relocation/fuzzy resolution.

P4-B deliberately does not persist source arrays, residency/LRU/protection, preload,
Difference/cache, Display Gain, analysis state, workers/tokens/generation,
derived Split/Difference documents, transient view state, ROI/Line state, or
temporary Picks. Settings schema remains v5.

The repository owner reported the focused P4-B Windows suite PASS (`36 passed`)
before PR #30 merged.

### P4-C — Session Persistence & Typed Recent — implemented, validation PASS, merge pending

P4-C generalizes new `.pixelscope` writes to **PixelScope Session v1** while keeping
legacy Comparison Set v1 read compatibility. The authoritative contract is
[`docs/SESSION_CONTRACT.md`](SESSION_CONTRACT.md).

Session v1 persists durable workspace intent rather than process state:

- Registered membership plus minimum RAW reconstruction metadata;
- exact ordered Selected paths;
- a Selected source-path Current Comparison Page anchor;
- applicable source Active and Primary plus stable layout;
- ROI, Line, Display Gain, and applicable Split Channels state;
- a regenerable Difference recipe only when saved Difference A/B both belong to the
  saved Current Comparison Page.

The Difference rule deliberately matches reader eligibility. A hidden active
Difference binding may survive page navigation under PR #33, but Session Save omits
that recipe after the user moves to a page that no longer contains A/B. Reopen never
creates an off-page Difference dependency or implicit calculation. For an eligible
saved recipe, Session restores the page and exact compatible panel intent, then
issues one explicit **Calculate** request; PR #33 alone establishes active Difference
provenance/result state.

Open is a single-read staged transaction. It validates first, stages incoming
registration identities before destructive replacement, preserves the prior workspace
when zero incoming registrations succeed, restores only the bounded foreground page,
and uses the existing P2/P3/P4 loading, residency, Display Gain, and Difference
pipelines. A MainWindow-owned eight-step overlay reports asynchronous reconstruction
without a nested event loop or new runtime authority. Temporary P4-A Picks and all
runtime arrays/caches/workers/tokens are not persisted.

File UX uses **Open Session... / Save Session...** plus typed bounded MRU menus for
Recent Images, Recent Folders, and Recent Sessions. Recent history is path-only,
best-effort observer metadata and remains outside Settings schema v5; missing entries
use Remove/Keep and legacy `recent/comparison_sets` is migration/read fallback only.

The repository owner reports the complete requested local validation set PASS on the
code/test head `b2865c37bd665b4a8a136aa3fe48c3c6a6fcc84b`, including the regression for
`>6 Selected → page-1 Difference → hide → page 2 → Save/Open` writer/reader symmetry.
Subsequent merge-closure changes are documentation/PR-metadata only.

### P4-D — Saved ROI & Analysis Workspace Productivity

Separate saved ROI definitions from the current active ROI that feeds analysis.
Define coordinate/dimension, naming, activation/deletion, and session ownership
before implementation.

### P4-E — Viewer Overlay & Export Productivity

Alpha Overlay must remain presentation-only. Export should address concrete
workflow pain points and define whether each artifact represents native data,
normalized Difference, presentation, analysis output, or session metadata.

### P4-F — Integration & Workflow Hardening

Harden P4-A through P4-E together against the inherited P2/P3 Current Comparison
Page, source residency, preload, Difference, Display Gain, RAW profile resolution,
request identity, and Qt lifetime contracts.

### Deferred from P4

Arbitrary-angle Line Profile is intentionally omitted. Line Profile is an
observation/sampling tool, so a future arbitrary-angle design should first define a
discrete sampling/pixel-path and coordinate-display contract. Interpolation is not
assumed, and the current utility does not justify that semantic/UI complexity.

## P5 — Remote IQA Platform

- Remote submission and result workflow.
- Server/job API.
- GPU worker.
- Artifact, heatmap, and result comparison.

## P6 — Identity, Access & Remote Operations

- Login and SSO.
- Token/credential lifecycle.
- Permission/access policy.
- Operational administration.

## P7 — Release Engineering & Distribution

- Exactly PyInstaller 5.7 `onedir`.
- Portable ZIP.
- Inno Setup.
- Clean-PC smoke testing.
- Signing.
- Update strategy.
- Repeatable release process.

## Deferred optimization outside the phase sequence

Schedule only when profiling/user-visible latency demonstrates need:

- preload concurrency one versus two;
- directional/bidirectional or deeper Folder Position preload;
- CPU/I/O aggressiveness controls;
- broader resource-policy Settings exposure;
- process-level memory/profiler telemetry;
- coalescing/debounce/cancellable chunking for large-image Display Gain stepping;
- native/SIMD gain optimization beyond current float32 fused affine processing.