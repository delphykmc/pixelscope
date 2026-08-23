# Engineering decisions

This file records the **currently effective** engineering decisions. Detailed historical
slice rationale remains available in completed execution plans and focused contracts
linked from `docs/ROADMAP.md`.

## Platform and implementation constraints

- CPython 3.10 x64 is fixed.
- PySide6 6.4.2 remains the Qt binding; pyqtgraph 0.13.3 provides image/plot primitives.
- PyInstaller is fixed at exactly 5.7 `onedir`; PyInstaller 6.x is prohibited.
- NumPy/OpenCV implementations come first. Native C/C++ optimization requires profiling
  evidence and remains behind numerical/image interfaces.
- Expensive I/O/numerical work runs in bounded workers; widgets do not own decode,
  Difference, full-frame Display Gain, or Remote IQA numerical algorithms.
- Native source dtype/channel meaning is preserved. Overflow-prone arithmetic promotes
  before subtraction/multiplication; full-frame display work avoids float64 promotion.
- Presentation transforms never redefine native source or analysis domains.

## Local workspace authority

- **Registered**, **Selected**, **Current Comparison Page**, **Presented**, and
  **Resident** are distinct runtime states.
- Selected is ordered logical membership and may exceed six.
- Current Comparison Page is a derived maximum-six working subset of Selected.
- `Analysis Working Set = Current Comparison Page`.
- Viewer slot identity is page-local `1..6`; global Selected ordinal is separate.
- `_fixed_geometry()` is the sole fixed Multi View geometry policy.
- Primary/focus ordering is page-local and never changes Selected membership/order.
- Selected membership alone is not generic residency protection; Current Comparison Page
  plus correctness dependencies owns protection.

## Input and RAW decisions

- **Open Images...** is selection-oriented and is the one top-level image-file open path
  for PNG/BMP/JPEG/RAW.
- **Open Folder...** is registration-oriented. Folder registration does not implicitly
  mutate Selected/current page/presentation.
- Direct file D&D follows Open Images intent; folder D&D follows registration intent;
  mixed D&D preserves both.
- RAW profile resolution is conditional logic inside the common input path, not a second
  top-level open workflow.
- Folder/session registration may keep RAW unresolved until foreground current-page use.
- RAW native source remains authoritative for Statistics/Histogram/Line/Split/Difference.
- 1× RAW display uses native effective full scale. Gain >1 uses Black-anchored
  `B + G * (X - B)`; Bayer tuple Black is CFA-specific; White Level remains metadata.
- Demosaic/WB/CCM/tone mapping and automatic Black/White estimation remain outside the
  current product boundary.

## Display Gain decisions

- The user-facing term is **Display Gain**, not Exposure.
- One session-local gain state supports 1×/2×/4×/8×/16×.
- Ordinary Gray/RGB use anchor 0; RGBA gains RGB and preserves alpha; RAW uses its
  metadata-derived anchor policy.
- Difference is excluded from general Display Gain and retains its own presentation Gain.
- 1× is a no-work canonical-preview reuse path; gain >1 derives presentation from
  resident native source on the existing bounded numerical pool.
- Display Gain never changes native source generation, residency identity, local analysis,
  or Difference-cache identity.

## Difference decisions

- Supported families are Gray↔Gray, RGB/RGBA↔RGB/RGBA, and same-CFA Bayer↔Bayer.
- Cross-family, size, CFA, and unsupported-layout mismatches are rejected; no implicit
  RGB→Gray conversion is performed.
- Equal effective depth uses native code-domain Difference.
- Mixed effective depth normalizes each source independently and stores canonical
  float32 absolute Difference in `[0,1]`.
- `DifferencePanel` remains the numerical/cache authority.
- Explicit **Calculate** is the only operation that establishes a new active Difference.
- Toolbar Diff is hide/show only after an active result exists.
- Keep Selection resets active Difference binding before Selected changes but does not
  purge valid generation-keyed Difference cache entries.

## P2 runtime/settings decisions

P2 is Complete. Current durable runtime rules are:

- `ApplicationSettings` + `SettingsRepository` own typed versioned preferences;
  QSettings is a persistence adapter.
- Decoded Source Memory accounts exact native `source.nbytes` only.
- `ResidencyManager` owns protected soft-budget LRU accounting/planning;
  `MainWindow` owns document mutation.
- One protected source may exceed the soft budget.
- Difference-cache and source-residency budgets are independent.
- Folder Position preload is `+1` only, one position deep, max-one preload worker;
  normal foreground load pool remains max two.
- Exact physically RUNNING preload may be logically promoted to foreground without
  duplicate decode when all request/generation/path/profile/token identities match.
- Runtime diagnostics are bounded, sanitized, deterministic, observation-only, and exposed
  through **Help > Copy Diagnostics** rather than a live monitor.

## P3 current-page decisions

P3 is Complete. Current rules are:

- Registration and Selected have no six-image limit.
- Current Comparison Page is the explicit max-six local working-set boundary.
- Ctrl+Left/Ctrl+Right moves non-wrapping Comparison Pages; Left/Right remains fine
  Selected-image navigation; PageUp/PageDown remains Folder Position.
- Current page is semantic authority for native analysis, load completion, and generic
  residency protection.
- Split Channels is transient presentation derived from one native source and does not
  create Registered/Selected subchannel identities.

## P4 workflow/session decisions

P4 is Complete through PR #35.

- Temporary **Pick** is source-document ID state only and owns no source/analysis work.
- Active, Primary, and Pick are separate states.
- **Keep Selection** is the only Pick operation that mutates Selected.
- Session v1 persists durable local workspace intent but no runtime arrays/cache/residency/
  workers, temporary Picks, generated Difference result, or remote runtime state.
- Legacy Comparison Set v1 remains read-compatible; new writes use Session v1.
- P4-C Recent Images/Folders/Sessions are typed max-10 path MRUs and best-effort observer
  metadata outside ApplicationSettings.
- Focused exports consume existing results/presentation and never become numerical/source
  authority.
- Saved/named/multiple ROI, Alpha Overlay/Flicker/Wipe, and arbitrary-angle Line Profile
  remain deferred.

## Remote IQA durable authority

Authoritative P5 documents:

- [`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md) — product/transport/ownership;
- [`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md) — current numerical/artifact contract;
- [`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md) — historical read-only schema v1;
- [`P5D_VIEWER_INSPECTION.md`](P5D_VIEWER_INSPECTION.md) — completed native Inspect;
- [`P5E_HISTORICAL_RESULTS.md`](P5E_HISTORICAL_RESULTS.md) — active historical workflow.

The governing numerical rule is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

### Result/version decisions

- `iqa_result_reader.load_result()` is the canonical version dispatcher.
- Schema v2 is current; schema v1 remains explicit historical/read-only compatibility.
- No synthetic v1→v2 numerical migration is allowed.
- Normal v2 open is summary-first: manifest + summary only.
- Deferred Scene grids remain bounded and are validated/materialized only on demand.
- COMPLETE and successful PARTIAL Scenes obey identical full Scene invariants.
- PARTIAL `scene_outcomes[]` carries failed/cancelled requested Scene diagnostics; no
  incomplete successful Scene is synthesized.

### Identity decisions

- `variant_id` is comparison-slot/IQA-Reference identity.
- `source_id` is concrete image identity.
- `scene_id` is Scene identity.
- `measurement_context_id` scopes server-authored weighted measurement to its Scene
  context.
- Display labels are never identity.
- Optional `storage_root_id` is source-location metadata only; it does not alter immutable
  source equality or measurement-context identity.

### Numerical/reduction decisions

- Server-authored W/S1/S2/count/valid plus normative formulas are measurement authority.
- Canonical Scene absolute mean is `ΣS1/ΣW`.
- Default absolute Dataset Overview is pooled weighted mean.
- Pair-valid support is target-valid ∩ reference-valid.
- Power Mode 1 is ratio of pair-valid aggregate weighted means.
- Power Mode 2 is arithmetic mean of finite pair-valid grid log ratios.
- Signed comparison is pair-valid target weighted mean minus reference weighted mean.
- Default relative Dataset Overview is arithmetic mean of valid Scene comparison values.
- IQA Reference is independent from local Primary.

## P5-B Results decisions — Complete / PR #38

- P5-B is the **sole** local IQA result workspace/controller.
- File, Remote Jobs, and P5-E Recent opens must converge on this same loader/workspace.
- Summary-first Absolute presentation is default.
- Reference preparation is off-thread and one Scene grid at a time; only derived scalar
  results are retained.
- Deferred failure restores last-valid presentation/control state.
- Passive result browsing never mutates local Files/Selected/Primary/native analysis/
  Difference/residency/preload/Session/Picks.

## P5-C storage/submission decisions — Complete / PR #42

- ApplicationSettings schema v6 owns `server_base_url`, logical `storage_roots[]`, and
  `staging_root_id`.
- Portable source/result location is **exactly** `storage_root_id + relative_path`.
- `client_path` is machine-local and is never portable request/result identity.
- Existing sources under configured roots use the most-specific matching root; outside
  sources may be content-addressed staged by SHA-256.
- P5-C owns root/path validation, resolved containment, atomic staging publication, and
  SHA-256 winner/reuse verification.
- Initial user-facing submission is exactly two variants A/B; result schema remains
  N-way-capable.
- Current Pair uses underlying Current Comparison Page order, not Primary/Active/view
  reorder.
- Folder Pair is immediate PNG/JPG/JPEG/BMP only, deterministic NFC lexical pair-by-index,
  equal non-zero count, equal dimensions, max 512 Scenes, and does not register/select the
  batch locally.
- Create POST is never blindly retried because timeout can be ambiguous after server
  acceptance.
- Terminal result-reference GET may use bounded idempotent recovery; completion never
  auto-opens Results.
- Live root changes use revision + re-resolution so stale mapping callbacks cannot win.

## P5-D viewer-linked inspection decisions — Complete / PR #43

Current merged main includes P5-D at
`b086443d188eb9daae4bbf4f0faab3ff1d114f93`.

- Native Scene inspection is **explicit** via **Inspect in Viewer**; passive Results never
  alter Selected.
- Every required unique source is resolved through P5-C and verified before local
  mutation: ordinary-image eligibility, dimensions, exact encoded-byte SHA-256, and decode.
- Verification is all-or-nothing. A source failure disables/fails Inspect without making
  the server Result corrupt.
- Repeated variant bindings may intentionally share one native `source_id`; PixelScope
  keeps one canonical Files/native source identity while preserving IQA aliases.
- First successful Inspect captures one transient Return snapshot. Newer local intent
  invalidates Return rather than being overwritten.
- P5-D uses existing Files/Selected/current page/viewer/residency owners and does not add a
  second source registry/viewer stack.
- Spatial overlay is vector/block presentation driven by schema-v2 geometry and canonical
  W/S1/S2/count/valid math.
- New Result open and shutdown cancel/drop feature-local Inspect/spatial work.

## P5-E historical Result decisions — Active / Draft PR #44

### Historical locator

- Portable production historical Result location is exactly
  `storage_root_id + relative_path`.
- A machine-local absolute locator is allowed only for manual/out-of-root or schema-v1
  history.
- Logical Recent reopen resolves through **current** Remote IQA settings and P5-C
  `resolve_result_reference()`; mapped drive/UNC paths are never portable history identity.
- Successful manual schema-v2 opens under configured roots canonicalize to the
  most-specific logical root.
- Jobs history preserves the server-published logical Result locator rather than deriving
  identity from the currently mapped local path.

### Recent IQA Results

- Recent IQA Results is independent observer metadata under `recent/iqa_results`.
- Payload version is 1; maximum retained entries is 10; ordering is MRU; deduplication is
  by locator identity.
- Malformed/future records are ignored within explicit bounds.
- Only successful canonical Result opens record history.
- File, Jobs, and Recent entry activation converge on P5-B.
- Missing/offline/remapped entries are retained until explicit Remove/Clear.
- P4-C Recent Images/Folders/Sessions and ApplicationSettings schema v6 remain unchanged.

### Historical identity/integrity

- A successful history record stores observed `result_id + schema_version`.
- No new whole-result digest is introduced.
- On Recent reopen, the canonical reader validates the artifact first; P5-E then compares
  observed identity **before** `IqaWorkspaceWidget.set_model()` changes presentation.
- Identity mismatch preserves the current last-valid Result and the existing Recent entry
  unless the user explicitly removes it.
- Structural/numerical integrity remains the canonical P5-A/P5-A2 reader's authority.

### Result-only and source verification

- A valid IQA Result remains browseable when original native sources are missing, offline,
  unmapped, changed, or not portably located.
- Result open must not perform a dataset-wide source stat/hash/decode pass.
- Source existence/containment/dimensions/exact encoded SHA/decode remain lazy P5-D Inspect
  responsibilities.
- Source failure never retroactively makes a structurally valid Result corrupt.

### Provenance

- Provenance lives **inside the existing Results workspace**.
- Schema v2 displays published Result identity/publication state, selected Scene
  measurement-context provenance, source IDs, optional storage roots, relative paths,
  SHA-256, dimensions, and current local native-inspection status.
- Provenance never decodes native pixels or recomputes IQA.
- Schema v1 is explicitly historical/read-only and receives no invented v2 metadata.
- PARTIAL remains PARTIAL; failed/cancelled Scene diagnostics remain existing P5-B/P5-C
  authority.

### Stale/lifetime composition

- P5-E installs after P5-D and wraps the already P5-D-wrapped P5-B open path.
- Therefore every historical open consumes P5-D new-result teardown before canonical load.
- P5-B Result generation remains rapid A→B latest-open-wins authority.
- P5-E keeps only the latest pending historical context.
- Logical Recent resolution also captures P5-C mapping revision; stale mapped-path work
  cannot publish after a remap.
- Close cancels P5-E feature-local resolver/pending context, then continues P5-D/P5-B
  teardown; durable remote jobs are unaffected.
- Session v1 remains unchanged and carries no IQA locator, Result identity, Reference,
  Scene, Provenance, Inspect, or Return state.

## P5-F handoff decisions — Planned

P5-F does not redefine P5-E correctness contracts. It is split into:

1. **P5-F1 Real GPU Server Compatibility**;
2. **P5-F2 SMB / Network / Grid Performance Characterization**;
3. **P5-F3 Cache / HTTP / Retry / Backoff Tuning**;
4. **P5-F4 Stress / Failure / Lifecycle Hardening**;
5. **P5-F5 Optional Detail Characterization + P5 Closure**.

Performance tuning is measurement-driven. No fixed wall-clock number is a correctness
gate. Correctness remains stable versioned identity/math/geometry, bounded ownership,
no duplicate work, stale-result rejection, and teardown safety.

## Current resource policy

- Difference Map Cache remains independent, byte-budgeted, persistence-free.
- Decoded source residency remains a protected soft-budget manager.
- Current Comparison Page plus correctness dependencies owns generic source protection;
  off-page Selected/Picked membership does not.
- Foreground load pool max remains two; preload pool max remains one; shared numerical
  pool remains bounded.
- Display Gain, IQA scalar/reference preparation, IQA historical metadata, Provenance,
  and spatial overlays do not enter decoded-source residency accounting.
- P5-F may tune remote/grid caches only from measured evidence and without creating a
  second source/residency authority.

## Validation and merge-state decision

Only validation actually observed on a named exact head may be recorded as PASS.

Current merged baseline is
`main@b086443d188eb9daae4bbf4f0faab3ff1d114f93` with P5-D Complete. P5-E is Active in
Draft PR #44. Focused tests are present on the branch, but this implementation environment
has not observed a current-head GitHub Actions or local repository validation PASS.
Owner Windows validation A–G, exact-head automated/full validation, independent latest-head
whole-PR review, and owner merge approval remain P5-E merge gates.
