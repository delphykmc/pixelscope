# Execution plan: P4 — Workflow & Session Productivity

Status: Active — P4-E merged as PR #34; P4-F implemented / owner validation and independent review pending
Owner: repository owner + P4 orchestration agents
Last updated: 2026-08-15
Inherited merged baseline: PR #34 / main
`79ee74134f1ebef9dd13f82e49f8e34407bb78f4`

## Goal

Complete the focused workflow-productivity program on top of the stabilized P2/P3
image semantics and bounded Current Comparison Page architecture. P4-C owns durable
Session/Recent workflow intent. P4-E exports only current analysis/presentation
results. P4-F closes P4 through cross-feature integration and lifetime hardening,
without adding another broad product feature.

P4 must improve workflow without creating a second source, analysis, cache,
selection, worker, preload, or residency authority.

## Inherited P2/P3 baseline

The following ownership hierarchy is authoritative:

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

```text
Analysis Working Set = Current Comparison Page
```

Inherited invariants:

- Selected alone is not decoded-source residency authority.
- Current Comparison Page plus correctness dependencies remains the bounded generic
  source-protection authority.
- Comparison Page navigation creates no speculative preload.
- P2 preload remains Folder Position `+1`, exactly one position ahead, max-one
  speculative worker, with existing RUNNING promotion semantics.
- Display Gain is presentation-only and never redefines native analysis/request
  identity.
- Difference remains native code-domain for equal effective depth and independently
  normalized `[0,1]` for mixed effective depth.
- RAW Black/White metadata and display transforms do not enter Difference domain
  selection/normalization.
- temporary workflow state must not become source/cache/residency/analysis authority.
- Current Comparison Page remains derived runtime state; durable Session persistence
  may store only a source-path page anchor needed to reconstruct the same page.
- PR #32 owns generic Display Gain/Difference worker and presentation stability.
- PR #33 owns active Difference establishment, provenance, visibility, teardown, and
  cache lifecycle; only explicit successful Calculate establishes an active result.
- export is a consumer of current canonical/result presentation and must not become
  numerical, source, residency, preload, or Difference authority.

## Program sequence

`P4-0 → P4-A → P4-B → P4-C → P4-E → P4-F → P4 Complete`

| Order | Slice | Status |
|---|---|---|
| 0 | P4-0 P3 Closure & P4 Program Setup | Complete — PR #28 |
| 1 | P4-A Review Selection & Curation | Complete — PR #29 |
| 2 | P4-B Comparison Set Persistence | Complete — PR #30 |
| 3 | P4-C Session Persistence & Typed Recent | Complete — PR #31 — `436033a0d99513fe8db35f08305395127e430af2` |
| 4 | P4-D Saved ROI & Analysis Workspace Productivity | Deferred |
| 5 | P4-E Analysis Export Productivity | Complete — PR #34 — `79ee74134f1ebef9dd13f82e49f8e34407bb78f4` |
| 6 | P4-F Integration & Workflow Hardening | Active — implementation/test/docs prepared; owner validation/review pending |

P4-D is intentionally skipped in the execution order. Session v1 already persists
the current active ROI/Line; the remaining named/multiple ROI manager needs product
semantics for ownership, mixed dimensions, and coordinates that are not yet justified
by a demonstrated workflow pain point.

Alpha Overlay is also deferred. Multi View, synchronized navigation, and Difference
already cover the principal comparison workflow; Overlay/Flicker/Wipe utility has not
been validated sufficiently to add pairing/alpha/Gain/Split/Session semantics.

Arbitrary-angle Line Profile is intentionally **not** a P4 slice. PixelScope's line
profile is an observation/sampling tool, so a future arbitrary-angle implementation
would require a deliberate discrete pixel-sampling/path and coordinate-display
contract rather than casually introducing interpolation. The expected utility does
not currently justify that semantic/UI cost.

## P4-0 — P3 Closure & P4 Program Setup — Complete

PR #28 merged at `e30c49d6759715228a820d673ad8939ea9a3afe8`.
The docs-only orchestration slice:

- recorded P3-E / PR #27 as merged and P3 as Complete;
- archived the completed P3 execution plan;
- established this P4 program plan;
- reconciled phase/status documentation;
- added no P4 runtime/UI state and changed no Settings/persistence schema.

## P4-A — Review Selection & Curation — Complete

### Goal

Allow a user to browse a large Selected set page by page, make temporary review
picks, then explicitly reduce Selected to the picked native images without changing
Files registration.

Authoritative flow:

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

### Implemented contract

P4-A merged as PR #29 at `3486146494076e9b513843b90ec44e504043729e`.

- There is **no explicit Review Select mode**. Eligible native source tiles in Multi
  View expose **Pick** directly; normal tile activation and navigation retain their
  inherited meanings.
- The first checked Pick captures the current ordered Selected IDs as the temporary
  baseline internally.
- `ReviewSelectionState` stores only baseline Selected IDs, picked native source
  IDs, and internal captured-baseline state. It stores no source/preview arrays,
  workers, caches, residency state, RAW-profile copies, or Current Comparison Page
  copy.
- The Pick text remains `Pick`. Checked membership uses the depressed/checked button
  state plus a bright-yellow tile-wide border; Active and Primary remain distinct.
- Picks remain marked while navigating across Comparison Pages. Off-page picks do
  not need to remain resident or protected.
- The presentation row exposes
  `Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection`.
  `Selected N` is the temporary Pick Set count, not the Files logical Selected count.
- **Clear Selection** clears only temporary picks.
- **Keep Selection** is disabled when the Pick Set is empty.
- Applying Keep Selection preserves original baseline Selected ordering among picked
  images rather than pick order.
- Non-picked images remain Registered in Files.
- Pick membership alone does not trigger decode, `_ensure_loaded()`, source LRU
  touch/protection, preload, foreground promotion, gained-preview generation,
  Difference calculation/cache changes, or analysis requests.
- Split/Difference derived presentation documents are not independent pick
  identities; picks refer to native registered/selected source document IDs.
- Only Keep Selection mutates logical Selected. Pick/Unpick/Clear Selection do not.
- There is no user-facing Cancel command.
- a different logical Selected-membership mutation invalidates the captured
  baseline/Pick Set before or with the existing normal selection mutation.
- registration-only folder input preserves the temporary curation state because it
  does not mutate Selected.
- P4-A Pick Set is not persisted across Session restore.
- Settings schema remains v5.

### Implementation shape

- `core.review_selection.ReviewSelectionState` is the Qt-free ID-only state model;
  its `active` field is internal captured-baseline state rather than product mode.
- `ui.review_selection.ReviewSelectionController` owns temporary direct-curation
  orchestration and the `Selected N / Clear Selection / Keep Selection` controls.
- `TileHeader` exposes the stable source-tile Pick affordance separately from its
  existing Primary flag. The viewer `reviewPicked` property drives the tile-wide
  yellow selected border independently from Active styling.
- production application composition places Display Gain before the row stretch and
  then inserts the curation controls, producing the owner-approved unwrapped order
  without moving unrelated Main-toolbar commands.
- `DocumentListWidget` pre/post selection/removal signals allow curation invalidation
  without runtime PySide signal disconnect/reconnect rewiring; MainWindow retains
  normal selection/removal mutation authority.
- Keep Selection delegates the resulting ordered subset through the inherited
  Selected mutation/render/source lifecycle rather than creating a
  curation-specific source lifecycle.

### Focused coverage

Focused suites cover:

- state capture/exit, Pick/Unpick, duplicate idempotence, Clear, zero-pick,
  temporary lifetime, and baseline-order filtering;
- direct first-Pick capture, stable Pick checked/depressed state, picked count, and
  Active/Primary/Pick separation;
- bright-yellow tile-wide Pick state and cross-page restoration;
- `1 / 2 / 6 / 7 / 15 / 50` Selected cases;
- cross-page picks for 7 and 15 images;
- ordered Keep Selection result and non-picked registration retention;
- exact Files-tree subset and first-result Active state after Keep Selection;
- 50-image page-bounded loading/protection with no Pick-owned preload;
- no Pick/Unpick/Clear `_ensure_loaded`, render, Statistics, Difference-input, or
  Line Profile request churn and no source-generation/residency/Difference-cache
  change;
- pan / Ctrl+drag ROI / Shift+drag Line Profile gestures not toggling Pick;
- Split/Difference derived identity rejection;
- programmatic, production Files removal, direct signal fallback, and direct-Files
  Selected replacement invalidation.

## P4-B — Comparison Set Persistence — Complete

### Historical artifact boundary

P4-B merged as PR #30 at `3a19589e6cbad5fa8c814c522df6a553f59ee340`.
It established the first external `.pixelscope` artifact with
`kind = "pixelscope-comparison-set"` and `schema_version = 1`.

The persisted source identity contract is a normalized **absolute local source
path**. The v1 reader rejects blank/relative source, Active, and Primary paths before
normalization. There is no relocation/fuzzy path resolution. Comparison Set v1 is
therefore deterministic but path-layout dependent and may disclose local paths.

Comparison Set v1 persists ordered logical Selected native-source references,
optional selected Active, optional applicable Primary, stable layout mode, and
minimum resolved RAW profile metadata needed to reconstruct a RAW source. It does
not persist runtime arrays, residency/LRU/protection, preload, Difference/cache,
Display Gain, ROI/Line, analysis results, workers/tokens/generations, or temporary
P4-A Picks.

P4-C supersedes **new writes/UI terminology** with Session v1 while preserving
legacy Comparison Set v1 read compatibility.

### Validation status

The repository owner reported the focused P4-B Windows suite PASS (`36 passed`)
before PR #30 merged.

## P4-C — Session Persistence & Typed Recent — Complete

### Goal and durable contract

P4-C merged as PR #31 at `436033a0d99513fe8db35f08305395127e430af2`.
P4-C generalizes the workflow artifact into **PixelScope Session v1**. New writes use
`kind = "pixelscope-session"`, schema v1, and `.pixelscope`; legacy P4-B
`pixelscope-comparison-set` v1 remains read-compatible.

Authoritative contract:
[`docs/SESSION_CONTRACT.md`](../../SESSION_CONTRACT.md).

Persist durable workspace intent only:

- Registered membership and resolved RAW reconstruction metadata;
- exact ordered Selected paths;
- a Selected source-path Current Comparison Page anchor;
- applicable source Active and Primary;
- stable layout mode;
- ROI and Line;
- Display Gain and applicable Split Channels state;
- a regenerable Difference recipe only when its A/B are both members of the saved
  Current Comparison Page.

Registered order is non-semantic; Selected order is semantic. Temporary Picks,
decoded arrays, previews, residency/LRU/protection state, preload/workers/tokens,
Difference maps/cache/results/documents, calculated analysis results, and other
derived buffers remain non-persistent.

### Restore transaction and PR #32/#33 boundary

Session Open is a single-read transaction. It validates first, probes paths without
decoding, stages incoming registrations before removing unrelated current workspace
members, and leaves the existing workspace/Picks intact if zero incoming sources
actually register.

After commit, restore clears stale P4-A curation, restores exact loadable Selected
order and the saved Current Comparison Page from the page anchor, then uses the
existing bounded foreground loader, Display Gain pipeline, ROI/Line state, and
DifferencePanel. There is no Registered-wide eager decode.

PR #32 remains the runtime/concurrency/presentation authority. PR #33 remains active
Difference authority. Session never pre-binds `_difference_source_ids`; an eligible
saved recipe restores exact compatible A/B/options on the reconstructed page and
issues one explicit **Calculate** request. The normal PR #33 result-ready path alone
establishes active Difference provenance/result/toolbar state.

Writer and reader use the same page eligibility. If an active Difference binding from
an earlier page remains after Diff is hidden and the user navigates elsewhere,
Session Save omits that off-page recipe. Session does not create special off-page
Difference loading/residency ownership or silently substitute another pair/page.

Session restore progress is reported by a MainWindow-owned child overlay with a
fixed eight-step procedure. It is an input shield/observer only: no `QDialog`, no
application-modal nested event loop, no Cancel/partial rollback contract, and no new
runtime authority.

### Typed Recent/Open UX

File UX is:

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

Recent history is an independent max-10 MRU per type. Image activation reuses the P3
selection-oriented path; Folder activation reuses registration-only behavior;
Session activation delegates to the Session controller. Missing entries use explicit
Remove/Keep. Wrong-kind or existing invalid artifacts remain history until explicitly
removed. History is path-only best-effort observer metadata, owns no source/runtime
state, and stays outside Settings schema v5. `recent/comparison_sets` is migration/read
fallback only; `recent/sessions` is authoritative.

### Validation status

The repository owner reports the complete requested local validation set PASS on
code/test head `b2865c37bd665b4a8a136aa3fe48c3c6a6fcc84b`. Coverage includes Session
schema/legacy read compatibility, strict validation/no-mutation, single-read and
registration commit boundaries, exact Selected/page/Primary/Active behavior,
RAW/display/ROI/Line/Split restoration, terminal analysis skip, real-worker
Difference reconstruction, restore-overlay lifetime, typed Recent persistence and
observer isolation, inherited PR #32/#33 regressions, and the final
`>6 Selected → page-1 Diff → hide → page 2 → Save/Open` writer/reader-symmetry case.

Merge-closure changes after this validated head were documentation/PR-metadata only.

## P4-D — Saved ROI & Analysis Workspace Productivity — Deferred

Session v1 already persists/restores the current active ROI and Line selection. The
remaining feature is effectively a saved/named/multiple ROI manager. Before such a
feature can be implemented safely, product semantics are needed for:

- session-global versus source-specific versus scene-specific ROI ownership;
- coordinate representation, bounds/clipping, and mixed image dimensions;
- naming/ordering/selection and activate/delete behavior;
- persistence ownership if a future Session schema intentionally adds saved ROI
  definitions.

No sufficiently concrete workflow pain point currently justifies those semantics.
P4-D is deferred and is not a P4 completion blocker. The existing active ROI remains
the sole ROI input to native analysis.

## P4-E — Analysis Export Productivity — Complete

Merged as PR #34 at `79ee74134f1ebef9dd13f82e49f8e34407bb78f4`.

### Goal

Export only the analysis/presentation results PixelScope already owns so they can be
reused in external engineering/reporting workflows. Do not add new numerical
algorithms and do not create a generic “export everything” framework.

Authoritative flow:

```text
native source
→ existing analysis/result owner
→ current result/presentation
→ export consumer
```

Export is never the numerical, Difference, source, analysis-working-set,
residency/preload, or generation authority.

### Implemented deliverables

1. **Export Difference Image...**
   - requires an explicitly established active Difference result;
   - current panel A/B must match active provenance;
   - current presentation identity `(pair/generation/domain/channel/mode/gain/threshold)`
     must match the last settled preview key, so returning to an active pair cannot
     relabel an old presentation with newly changed controls;
   - writes PNG from the same settled Difference presentation preview used by the
     current semantic filename;
   - reflects current Absolute/Mask, threshold, Difference display gain, and
     compatible channel/presentation state;
   - never screenshots toolbar/window chrome, never recalculates Difference, and
     never promotes a cached-but-inactive map to active state;
   - full-frame PNG encode/file I/O reuses the existing bounded analysis worker pool.
2. **Export Histogram CSV...**
   - serializes exact current plotted Histogram series;
   - deterministic rows identify Full image/Active ROI scope and bounds,
     source/series/channel, native bin edges and raw counts, current display bin
     edges, and current x/y presentation modes;
   - Gray/RGB/Bayer series follow current supported/rendered behavior with no new
     histogram calculation.
3. **Export Line Profile CSV...**
   - serializes exact current plotted Line Profile series;
   - deterministic rows identify current line coordinates, source/series/channel,
     x/y presentation mode, sample index/position, and current rendered value;
   - sampling/interpolation semantics are unchanged.
4. **Statistics / metrics productivity**
   - File-menu Statistics export and the main toolbar Export action share the same
     timestamped P4-E controller path while preserving existing Statistics CSV data
     semantics;
   - Difference metrics can be exported locally as deterministic CSV with source A/B,
     region, channel, comparison domain, effective bit depths, metric identity, and
     value;
   - Channel statistics and Difference metrics expose full-table CSV clipboard copy
     controls with headers;
   - all default analysis-export filenames include `YYYYMMDD-HHMMSS-mmm`; user-edited
     filenames remain respected;
   - Difference PNG default names encode channel/mode plus only the applicable gain
     or threshold/domain unit.
5. **Analysis presentation/lifecycle polish**
   - Statistics headings are `Region`, `Images`, and `Channel statistics` with clear
     title emphasis and the Channel statistics Copy control beside its heading;
   - Difference metrics has a local heading, CSV, and Copy controls while redundant
     native Scope/Domain helper rows are removed; normalized mixed-bit context remains
     visible when semantically necessary;
   - Statistics Copy, Difference Calculate, Difference metrics CSV, and Difference
     metrics Copy share one subtle command interaction model: transparent normal
     chrome, hover-revealed button chrome, recessed pressed feedback, keyboard-focus
     accent, and low-contrast/etched disabled state; Copy glyphs use the larger
     18 px presentation;
   - controller shutdown disarms late table/model callbacks and running PNG worker
     completion from touching deleted UI during MainWindow close/recreation.

Exports reuse the existing configured Export directory and successful last-directory
behavior. No new Export Settings schema is introduced. Missing/in-flight or stale
results disable or safely no-op the corresponding export. Cancel mutates nothing;
write failure gives compact status feedback.

### Explicit exclusions

P4-E does not add Saved/Named/Multiple ROI, Alpha Overlay, Flicker, Wipe, generic
screenshot/viewer capture, raw-source export, Difference numerical-map interchange,
Session export redesign, P4-A Pick export, arbitrary-angle Line Profile, new
Difference/Histogram/Line algorithms, source residency/preload redesign, Display
Gain/RAW redesign, Settings schema bump, remote IQA, or packaging/release work.

**Alpha Overlay is deferred by owner decision.** Overlay/Flicker/Wipe UX has not been
validated against the current Multi View + synchronized navigation + Difference
workflow, so P4-E does not add unproven pairing/alpha/Gain/Split/Session semantics.

### Focused validation

Deterministic coverage includes:

- exact current Difference Absolute/Mask presentation PNG export;
- active A/B provenance and settled-presentation freshness, including
  `A/B Calculate → uncached C/D → control change → A/B return` stale re-entry;
- filename/PNG-byte agreement after the current presentation settles;
- inactive/no Difference unavailable; explicit Calculate remains required;
- export calls no Difference recalculation and changes no source generation/cache;
- Histogram exact visible series with deterministic Gray/RGB/Bayer and ROI/full
  scope identity;
- Line Profile exact current rendered series/sample ordering;
- Difference metrics CSV and Statistics/Difference table clipboard CSV;
- timestamped default paths and custom-name preservation;
- Statistics File-menu/toolbar export parity;
- no-result safe action state/no-op;
- configured Export directory reuse, cancel/no-path no mutation, compact write
  failure;
- Selected/Active/Primary/Page, normal/preload workers, and production File-menu
  wiring remaining unchanged;
- idempotent composition/teardown behavior without duplicate export actions/signals;
- late model callback shutdown safety; and
- MainWindow close/recreate while a Difference PNG worker is physically running.

The repository owner reported the requested focused Windows validation and post-fix
static checks PASS on code/test head
`d8fa4b0c0ffe0a3517d37c703c490ec399f8ccf9`. Subsequent merge-closure commits were
documentation/PR-metadata only. This evidence is historical P4-E evidence and is not
P4-F-head validation.

## P4-F — Integration & Workflow Hardening — Active / P4 closure

P4-F closes P4 with cross-feature integration rather than another broad feature.
Existing P4-A/P4-C/P4-E and PR #32/#33 suites remain authoritative for subsystem
semantics; P4-F adds tests only for transition gaps between those suites.

### Coverage inventory and integration audit

- **Large selection / curation:** inherited P4-A coverage already exercises
  `1/2/6/7/15/50` Selected, cross-page Pick persistence, baseline-order Keep,
  50-image bounded page loading/protection, and no Pick-owned preload. P4-F does not
  duplicate those semantics.
- **Curation × Difference:** PR #33 remains active Difference authority. P4-F adds a
  production-composition path through Calculate → hide → Pick/Keep → Session Save,
  proving Keep tears the established Difference down before Selected mutation and
  the saved curated Session contains no stale old recipe.
- **Display Gain × Difference/navigation:** PR #32 remains numerical/worker authority.
  P4-F audits the application-global Gain subscription boundary and hardens closed
  MainWindow lifetime without changing gain math or pool policy.
- **Session round-trip:** P4-C remains authoritative for Registered/Selected/page,
  ROI/Line/Gain/Split/RAW and explicit-Difference reconstruction. P4-F adds a writer
  regression proving Current Comparison Page anchor persistence is independent from
  Active/Primary fallback state.
- **Later-page Session edge:** existing P4-C coverage remains authoritative for
  `page 1 Difference → hide → page 2 → Save/Open`, including omission of off-page
  Difference intent. The P4-F writer fix makes the saved page identity explicit.
- **Session × RAW:** existing P3/P4-C tests cover resolved reconstruction metadata,
  unresolved lazy RAW, foreground prompt terminal/cancel behavior, bounded current-
  page loading, and no Session speculative preload. Audit found no new P4-F semantic
  gap requiring a RAW code change.
- **Typed Recent:** existing P4-C suites cover canonical Image selection intent,
  Folder registration-only intent, Session controller delegation, missing Remove/Keep,
  invalid-existing retention, max-10 per type, and observer-only ownership. Audit
  found no new authority gap.
- **Export:** P4-E remains authoritative for exact Statistics/Histogram/Line/Difference
  current-result consumption. P4-F adds Session restore → explicit Difference
  reconstruction → settled Difference PNG export and asserts export does not invoke
  Calculate or mutate source generations/Difference cache.
- **Qt lifetime:** P4-E already covers late export model callbacks and close/recreate
  with a physically running PNG worker. P4-F adds application-global Display Gain
  close disarming so a closed-but-not-yet-destroyed window cannot start new gained
  preview work after another window changes/resets Gain.

### Bugs found and minimal fixes

1. **Session writer page-anchor fallback gap**
   - Contract: Session page identity is durable intent independently of Active.
   - Root cause: the writer omitted `page_anchor_path`, allowing the model fallback
     chain to derive it from Primary/Active/Difference/first Selected.
   - Fix: save the first persistent source of the actual Current Comparison Page as
     the explicit anchor. Schema and reader semantics are unchanged.
   - Regression: later-page save with Active/Primary unavailable still persists the
     correct page anchor.
2. **Closed-window Display Gain subscription gap**
   - Contract: application-global Gain state must not make a closed MainWindow a
     future work owner.
   - Root cause: each viewer/control remained directly connected to application-
     global `DisplayGainState` until QObject destruction; `close()` can leave the
     Python/Qt object alive long enough for a later Gain change to request another
     full-frame preview.
   - Fix: a MainWindow-owned lifetime guard disarms that window's Gain callbacks on
     `QEvent.Close` and cancels viewer-local gain previews. No new worker pool or
     numerical path is introduced.
   - Regression: changing global Gain after close starts no preview worker in the
     closed window.

### Runtime/resource invariants

P4-F does not change source residency accounting (`exact native source.nbytes`), the
Current Comparison Page protection authority, Difference generation/cache identity,
P2 `+1` Folder Position max-one preload, PR #32 worker pools, or PR #33 active
Difference lifecycle. Off-page Selected/Picked remains evictable. Session remains
metadata plus bounded foreground reconstruction; Export remains current-result
consumption and starts no preload/analysis recalculation.

### Focused P4-F tests

`tests/ui/test_p4f_workflow_hardening.py` covers:

- explicit later-page Session anchor independent from Active/Primary fallback;
- active Difference → temporary Picks → Keep Selection → Difference teardown →
  curated Session Save with no stale recipe;
- MainWindow close → later application-global Gain change with no old-window gained
  preview work; and
- Session restore → explicit Difference reconstruction → settled Difference PNG
  export with no export-triggered Calculate and no generation/cache mutation.

### Owner Windows manual workflow matrix

Before merge, owner characterization should cover:

- **Input/navigation:** Open Images, Open Folder, direct/folder D&D, 7/15/50 Selected,
  Comparison Page navigation, Selected-image navigation, Folder/Test Case position.
- **Curation:** cross-page Pick, Clear Selection, Keep Selection, and Active/Primary
  behavior after Keep.
- **Analysis:** Statistics, Histogram, ROI, Line Profile, Difference Absolute/Mask,
  Display Gain, Split Channels.
- **Difference lifecycle:** explicit Calculate, hide/show, source navigation, Keep
  teardown, and no stale document/provenance/toolbar/navigation result.
- **Session/Recent:** Save/Open Session, later-page restore, ROI/Line/Gain/Split,
  eligible Difference reconstruction, Recent Image/Folder/Session, missing entry
  Remove/Keep.
- **Export:** Statistics CSV, Histogram CSV, Line Profile CSV, Difference metrics
  CSV/Copy, and settled active Difference PNG.
- **Runtime:** small source-memory budget, eviction/revisit, preload enabled, Session
  open, Difference/Gain activity, close/recreate, and close with physically pending
  work where practical.
- **RAW:** resolved RAW, unresolved/lazy RAW, sidecar, cancel/retry, and no off-page
  eager prompt/decode.

No wall-clock threshold is a merge gate; the deterministic merge gates are bounded
ownership, request identity, no duplicate work, stale rejection, and teardown safety.

### P4 closure plan

P4 remains Active while this P4-F PR is unmerged. After owner validation,
independent review, and merge:

1. confirm latest `main` and the P4-F merge SHA;
2. create a small docs-only closure branch/PR;
3. mark P4-F = Complete and P4 = Complete;
4. archive this active plan as
   `docs/exec-plans/completed/p4-workflow-session-productivity.md`;
5. update `CURRENT_STATE`, `ROADMAP`, and UI status to the final merged baseline;
6. retain Saved/named/multiple ROI, Alpha Overlay/Flicker/Wipe, and arbitrary-angle
   Line Profile as future candidates, not incomplete P4 blockers.

No P5 runtime implementation starts as part of P4-F or the closure docs PR.

## P4-A explicit exclusions

P4-A does not add:

- Session/Comparison Set serializer/loader or `.pixelscope` file format;
- Recent Images/Folders/Sessions;
- Pick Set persistence or Settings schema changes;
- Saved ROI runtime/UI;
- arbitrary-angle Line Profile or interpolation/sampling redesign;
- Alpha Overlay or export behavior;
- source residency or preload policy/concurrency changes;
- Difference or Display Gain numerical changes;
- RAW Profile Library/CRUD/favorites/search, demosaic, white balance, CCM, or tone
  mapping;
- remote IQA/authentication or packaging/signing/installer behavior;
- broad MainWindow redesign.

## P4-B historical exclusions

P4-B itself did not add full Session persistence, Recent-entry history, Saved ROI,
arbitrary-angle Line Profile, Alpha Overlay/export workflows, source residency or
preload redesign, Difference/Display Gain numerical changes, RAW Profile Library or
processing, remote IQA/authentication, or packaging/release work. P4-C intentionally
extends the external artifact beyond that historical P4-B boundary.

## P4-C explicit exclusions

P4-C does not persist or own decoded source arrays, preview buffers,
residency/LRU/protection state, preload plans/workers, Difference maps/cache/results,
calculated analysis results, temporary P4-A Picks, request tokens/generations, or
other runtime/process state. It does not change generic PR #32 worker/concurrency
policy or PR #33 Difference lifecycle.

## Validation policy

Runtime/UI slices use owner/local Windows validation. Chat implementation agents do
not bootstrap/search for a local Windows virtual environment or install dependencies.
Earlier P4-E owner evidence is not reused as validation for the P4-F head.

Run the focused P4-F integration slice first:

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
    tests\ui\test_p4f_workflow_hardening.py
```

Then run the standard repository contract before merge:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

P4-F owner Windows validation is currently pending. Only observed results may be
recorded as PASS.
