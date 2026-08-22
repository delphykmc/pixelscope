# PixelScope current state

Snapshot date: 2026-08-22
Current merged `main`: `ad3721e28b759e75d8e0f4a28b003a4dd22f0f4a`

`main` includes:

- P5-A / PR #37 — historical executable schema-v1 compatibility;
- P5-A2 Stage 1 / PR #39 — durable schema-v2 contract;
- P5-A2 Stage 2 / PR #40 — executable schema-v2 reader/domain/math;
- P5-B / PR #38 — IQA Workspace & Local Result Exploration, merged at
  `a44978db783ebcecb0d55f8abb52b583e0fdc47c`;
- PR #41 — repository Ruff-format baseline, merged into current main.

P5 **Remote IQA Platform** is currently Active in **P5-C — Submission & Shared
Storage**, Draft PR #42 on `feature/p5-c-submission-shared-storage`.

Active plan:
[`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).

Durable P5 product/transport contract:
[`REMOTE_IQA_CONTRACT.md`](REMOTE_IQA_CONTRACT.md).

Current numerical/result contract:
[`REMOTE_IQA_V2_SPEC.md`](REMOTE_IQA_V2_SPEC.md).

Historical schema-v1 compatibility contract:
[`REMOTE_IQA_V1_SPEC.md`](REMOTE_IQA_V1_SPEC.md).

## Authoritative local workspace model

PixelScope retains the P3/P4 ownership hierarchy:

```text
Registered
    ↓ user selection
Selected
    ↓ Selected ordering + page offset / page size 6
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

- **Registered** is Files/catalog membership and is not limited to six.
- **Selected** is ordered logical comparison membership and may exceed six.
- **Current Comparison Page** is a derived bounded maximum-six working set.
- **Presented** is current viewer representation.
- **Resident** is decoded native source retained under P2 residency policy only while
  a correctness/runtime owner requires it.

`Analysis Working Set = Current Comparison Page`.

Viewer slots are page-local `1..6`; global Selected ordinal and viewer slot are
separate concepts.

Remote IQA remains a parallel feature-local job/result domain. Submission, Jobs, and
passive result browsing do not create a second Files/Selected/source-residency
authority.

## Current local input policy

Supported local PixelScope image families remain:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

- **Open Images...** and direct-file drag/drop are selection-oriented.
- **Open Folder...** and folder drag/drop are registration-oriented.
- Folder registration does not replace Selected or presentation state.
- Registered-but-unselected is valid.
- unresolved folder RAW remains lazy until foreground intent requires profile
  resolution.

Remote P5-C submission is intentionally narrower:

```text
.png  .bmp  .jpg  .jpeg
```

There is no silent RAW conversion for Remote IQA.

## P2/P3/P4 authorities inherited by P5

P5 does not redesign:

- exact native `source.nbytes` decoded-source residency accounting;
- independent source and Difference memory budgets;
- current-page/correctness source protection;
- off-page Selected/Picked sources remaining evictable;
- Folder Position `+1` max-one speculative preload;
- RUNNING preload foreground promotion;
- application-owned bounded analysis/Display Gain workers;
- native `ImageDocument.source` authority for local Statistics, Histogram, Line
  Profile, Difference, and Split Channels;
- Display Gain as presentation-only state;
- explicit Difference Calculate as the only active-Difference establishment path;
- P4-A temporary Pick/Keep curation;
- Session v1 and typed Recent Images/Folders/Sessions.

Remote IQA values are server-authored IQA measurements and must not be presented as
native PixelScope Statistics/Difference output.

## Current IQA result authority — executable schema v2

The governing rule is:

> **Server owns measurement; PixelScope owns reference-dependent comparison,
> reductions, and visualization.**

Schema v2 distinguishes:

- `variant_id` — comparison configuration / IQA Reference slot;
- `source_id` — one concrete source image;
- `scene_id` — evaluation Scene;
- `measurement_context_id` — Scene context that governs the published weighted
  measurement.

For every published successful Scene, including successful Scenes inside PARTIAL:

- every declared variant is present exactly once in top-level variant order;
- source dimensions and required physical geometry are compatible/exact as specified;
- PixelScope never aligns, resizes, imputes, or index-zips incompatible grids.

Server measurement authority remains W/S1/S2/count/valid. Canonical Scene absolute
mean is `ΣS1/ΣW`. Dataset absolute summaries expose pooled-weighted and equal-Scene
statistics; the default absolute Overview is `pooled_weighted_mean`.

Reference-dependent comparison is local and uses pair-valid support. The two power
modes remain ratio-of-weighted-means and mean-of-finite-grid-log-ratios. Signed
attributes retain signed target-minus-reference semantics. The default relative
Dataset Overview is the arithmetic mean of valid Scene comparison values.

Schema v1 remains explicit read-only historical compatibility and is never silently
upgraded to v2.

## P5-B merged result workspace

P5-B / PR #38 is now merged and owns the canonical local result-browsing path:

- **File > Open IQA Result...** uses canonical version dispatch;
- schema v2 opens summary-first and defaults to Absolute;
- N-way `variant_id` Reference switching is supported;
- Reference-dependent preparation runs off the Qt thread and processes one Scene grid
  at a time while retaining derived scalar results rather than the full grid corpus;
- Absolute/Relative table and Scene Trend presentation reuse the canonical v2 math;
- Scene cards expose published identity/path/hash metadata only;
- IQA Reference remains independent from local Primary;
- IQA dock float/dock/maximize/reset behavior follows the Plots workspace pattern;
- passive result browsing does not mutate Files, Selected, Current Comparison Page,
  Difference, source residency/preload, native analysis, Session, or Picks.

P5-D still owns logical-root/hash-verified **native source Inspect** and viewer-linked
spatial inspection.

## P5-C active client workflow

P5-C extends the existing single IQA dock to:

```text
IQA
├─ Setup
├─ Jobs
└─ Results
```

### Settings ownership

Application settings schema is now v6 and adds typed machine-local
`RemoteIqaSettings`:

```text
server_base_url
storage_roots[] {
    storage_root_id
    client_path
}
staging_root_id
```

`storage_root_id + relative_path` is portable identity. Windows/UNC client paths are
machine-local configuration only. Server physical paths and credentials are not
stored in PixelScope result/session artifacts.

### Submission identity

Initial user-facing submission remains exactly two variants `A/B`.

Current Pair is the **A/B pair of underlying Current Comparison Page documents**.
Primary, Active, viewer reorder, Display Gain, Difference, and Split presentation do
not redefine submission identity.

Folder Pair uses immediate eligible non-symlink files, Unicode-NFC deterministic
lexical ordering, equal eligible counts, pair-by-index pairing, equal pair dimensions,
and at most 512 Scenes.

Requests serialize only portable source identity and integrity metadata:

```text
storage_root_id
relative_path
sha256
width
height
```

Existing files under a configured logical root are referenced in place. Other files
may be content-addressed into the configured staging root using SHA-256 plus `.part`
publication and atomic final publication/reuse verification.

### Job API

Current P5-C client API is:

```text
POST /v1/iqa/jobs
GET  /v1/iqa/jobs/{job_id}
GET  /v1/iqa/jobs/{job_id}/result
POST /v1/iqa/jobs/{job_id}/cancel
```

Polling is used; WebSocket is not required.

Terminal states are:

```text
succeeded  partial  failed  cancelled
```

Only `succeeded` and `partial` may resolve a published schema-v2 result reference.
Completion never auto-opens Results. `Open Result` is explicit and delegates to the
existing P5-B canonical loader/controller.

Create POST is never automatically retried. Terminal `GET /result` recovery is
bounded and idempotent: after the initial attempt, retry delays are 1s, 2s, 4s, and
8s. Retry exhaustion keeps the terminal job visible and does not resubmit it.

### Executable PARTIAL result

P5-C extends schema v2 without a schema-version bump:

- `publication_state = "partial"`;
- ordered `scene_outcomes[]` covers every requested Scene;
- statuses are `succeeded`, `failed`, or `cancelled`;
- failed/cancelled outcomes carry bounded error diagnostics;
- at least one Scene succeeds and at least one fails/cancels;
- `scenes[]` contains only fully published successful Scenes in request order;
- every successful Scene still satisfies the same v2 numerical/geometry/cardinality
  invariants as COMPLETE;
- zero-success terminal work is FAILED/CANCELLED, not PARTIAL;
- all-success terminal work is SUCCEEDED/COMPLETE.

P5-B Results displays PARTIAL status plus failed/cancelled Scene diagnostics while
continuing to explore the published successful Scenes.

## P5-C debug/validation harnesses

Debug-only features are gated by `PIXELSCOPE_REMOTE_IQA_DEBUG` and are not production
workflow authority.

- **Request Inspector** runs the production request builder but stops before HTTP
  POST.
- **Replay JSON** accepts a bounded logical terminal job/result record, resolves it
  through current settings, injects Jobs, and still requires explicit Open Result.
- **Deterministic result generator** reuses the canonical v2 fixture writer and then
  validates through the canonical result loader.
- **Localhost fault server** uses real TCP/HTTP via stdlib `ThreadingHTTPServer` to
  exercise the production `HttpIqaJobClient`; it does not perform IQA computation.

Supported localhost fault scenarios include normal, PARTIAL, failed/cancelled,
create/status/result 5xx, one-shot result 500, malformed JSON, slow status, wrong job
ID, and wrong schema.

## Current validation evidence

Only observed owner evidence is recorded.

Historical full-suite checkpoint:

- `04f8c08ad77681d84ec934c902db8f8d03376e34` — full pytest PASS (809 tests), Ruff,
  mypy, and diff checks PASS. This predates later P5-C stages and is not claimed for
  the current head.

Later validated checkpoints:

- Setup UX + Request Inspector through `41384ec...`: focused behavior/static PASS;
- Replay JSON + deterministic COMPLETE result through repaired Stage-3 head
  `444391d...`: focused tests and manual replay/Open Result PASS;
- Stage-4 pre-formatting focused suite: **26 passed**;
- Stage-4 mypy: **102 source files, no issues**;
- manual real-socket `normal`: POST → status polling → result-reference success;
- manual `result-500-once`: first terminal `GET /result` returned HTTP 500, automatic
  result-reference retry returned 200 without resubmitting the same job;
- the owner repeated that recovery with a second newly created job and again observed
  terminal `succeeded`, enabled Open Result, and successful result browsing.

A latest-head repository-wide/full validation PASS is **not yet claimed**. Static
re-check after the Stage-4 formatting repair and final full validation remain required
before merge.

## Remaining P5-C merge blockers

The current implementation is not merge-ready solely because the HTTP happy path and
transient-result recovery work. Independent review identified remaining lifecycle and
storage hardening:

1. shared staging cross-process concurrency and symlink/junction containment;
2. cooperative cancellation/shutdown while staging/preparing create work is already
   running;
3. duplicate in-flight submit prevention and explicit ambiguous-create handling for a
   timeout after possible server acceptance;
4. settings-change/result-path remap race while a prior resolution worker is in
   flight;
5. final durable-doc validation, latest-head full owner validation, and independent
   whole-PR re-review.

P5-D must not start and PR #42 must not merge until these blockers are resolved and the
final gates pass.

## Forward sequence

```text
P5-C closeout
    ↓
P5-D Viewer-linked Scene Inspection
    ↓
P5-E Historical Result Workflow
    ↓
P5-F Integration & Performance Hardening
    ↓
P5 Complete
    ↓
P6 Identity, Access & Remote Operations
    ↓
P7 Release Engineering & Distribution
```
