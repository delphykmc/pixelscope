# P5-E — Historical Remote IQA Results

Status: **Active — Draft PR #44**

Base: `main@b086443d188eb9daae4bbf4f0faab3ff1d114f93`

P5-E adds bounded historical-result discovery and provenance around the existing
Remote IQA result workflow. It does not create a second parser, result model,
workspace, source registry, viewer, or numerical authority.

## 1. Authority and composition

The production path remains:

```text
File > Open IQA Result...
Jobs > Open Result
Open Recent IQA Results
        ↓
P5-E typed locator / identity context
        ↓
P5-D new-result teardown
        ↓
P5-B canonical asynchronous result loader
        ↓
P5-A2 v2 / P5-A v1 reader dispatch
        ↓
existing IQA Results workspace
        ↓ optional
P5-D Inspect in Viewer
```

P5-E may reject a historical reopen after the canonical reader has successfully
identified the artifact but **before** `IqaWorkspaceWidget.set_model()` changes the
currently presented Result. All artifact structural/numerical validation remains owned
by the existing readers and explorer model.

## 2. Historical Result Locator

### 2.1 Production logical locator

A portable production historical locator is exactly:

```text
storage_root_id + relative_path
```

The locator carries no mapped drive/UNC path. Reopen resolves it through the current
machine's `RemoteIqaSettings` and the P5-C `resolve_result_reference()` authority, which
revalidates the configured root, portable relative path, resolved containment, and
result-directory availability.

Jobs retain the logical locator published by the server rather than deriving identity
from the currently mapped local path.

A successful manual schema-v2 open may canonicalize to the most-specific configured
logical root only when the P5-C resolver can resolve that proposed logical locator back
to the **same canonical opened Result directory**. Lexical root membership alone is not
enough. A junction/symlink escape, unavailable root, or other proposed locator that
cannot reproduce the same canonical directory remains a Local locator.

### 2.2 Local locator

A machine-dependent absolute local locator is allowed for:

- manual/out-of-root Results;
- manual schema-v2 Results that cannot be reproduced by the production logical-root
  resolver;
- historical schema-v1 Results.

It is explicitly not a portable production identity.

### 2.3 Reopen identity

Recent stores the identity observed after a successful canonical load:

```text
result_id + schema_version
```

No new whole-result digest is introduced. On Recent reopen, the observed identity must
match the stored identity before presentation changes. A mismatch is treated as a
historical-location replacement/mutation, not as a valid continuation of the old entry.
The old current Result and Recent entry are preserved unless the user explicitly removes
the entry.

## 3. Recent IQA Results

Recent IQA Result history is independent observer metadata.

- storage key: `recent/iqa_results`;
- payload version: `1`;
- maximum retained entries: `10`;
- ordering: MRU;
- deduplication: locator identity, not `result_id`;
- malformed/future individual records: ignored;
- oversized/malformed container: ignored as untrusted observer state;
- successful File, Jobs, and Recent opens: recorded;
- failed/unsupported/corrupt/identity-mismatch opens: not recorded;
- missing/offline/remapped entries: retained until explicit Remove/Clear.

This metadata is not part of `ApplicationSettings`, does not increment the settings
schema, and does not modify P4-C Recent Images/Folders/Sessions.

## 4. Result-only mode

A valid published IQA Result remains useful even when native Scene sources are:

- missing;
- offline;
- unmapped on the current machine;
- moved or replaced;
- published without a portable source locator.

Result open therefore does **not** perform a dataset-wide native source stat/hash/decode
pass. The existing P5-B summary-first behavior remains intact.

Native source existence, resolved containment, dimensions, encoded-byte SHA-256, and
decode verification remain explicit P5-D **Inspect in Viewer** responsibilities. A
source failure can disable native inspection while the server-authored Result remains
browsable.

## 5. Provenance

P5-E adds one passive **Provenance** page inside the existing Results workspace.

For schema v2 it displays published metadata including:

- `result_id`;
- `schema_version`;
- COMPLETE/PARTIAL publication state;
- historical locator;
- variant/Scene/attribute counts;
- selected Scene `measurement_context_id`;
- representative/preprocessing/model/weighting/geometry provenance IDs;
- per-variant `source_id`;
- published source `storage_root_id` when present;
- `relative_path`;
- source SHA-256;
- width/height;
- current local native-inspection status.

The page never decodes native pixels and never recomputes IQA values. Its local
inspection availability is observer state derived from the **current** machine-local
Remote IQA root mappings. The existing P5-C/P5-D settings-change chain remains the
authority; P5-E observes that chain and refreshes Provenance immediately after a live
root add/remove/remap without requiring Result reopen or Scene reselection.

For schema v1 the UI explicitly labels the Result historical/read-only and displays only
metadata actually present in v1. P5-E does not synthesize v2 storage roots,
measurement-context provenance, N-way variants, or absolute source measurements.

## 6. COMPLETE and PARTIAL

P5-E does not alter P5-C/P5-B publication semantics.

- COMPLETE remains COMPLETE.
- PARTIAL remains PARTIAL.
- successful Scenes remain browseable;
- failed/cancelled Scene diagnostics remain visible through the existing Results UI;
- no failed Scene is synthesized into a successful Scene for history/provenance.

## 7. Stale work and lifetime

P5-E layers on top of the canonical P5-B generation and P5-D teardown contracts.

- every newer Result-open intent invalidates P5-E feature-local logical-Recent
  resolution **before** entering or superseding the canonical loader;
- cancellation is best-effort only; stale logical-resolution callbacks are rejected by
  a P5-E resolver generation even if the underlying worker completes later;
- after locator resolution, each new Result open advances the P5-B Result generation;
- rapid A→B open accepts only the latest canonical Result callback;
- one P5-E pending context is retained for the latest canonical generation;
- logical Recent resolution captures the P5-C mapping revision;
- a mapping change before presentation rejects/re-resolves stale work;
- new Result open first consumes P5-D's existing inspection/spatial teardown;
- close invalidates/cancels the feature-local logical-locator resolver and clears pending
  context;
- closing PixelScope never cancels durable remote server jobs.

Therefore a delayed logical Recent A cannot start a later canonical open after the user
has already chosen newer File/Jobs Result B. History and Provenance follow only the
accepted latest open.

## 8. Session boundary

Session v1 is unchanged. It carries no IQA Result locator, Result identity, Reference,
Scene selection, Provenance state, or native Inspect state.

Any future Session-carried IQA state requires an explicit Session schema/version design
decision outside P5-E.

## 9. Automated regression matrix

Focused automated coverage must include:

1. locator/Recent payload round-trip;
2. malformed, traversal, and future-version metadata rejection;
3. max-10 MRU and locator dedup;
4. most-specific manual-v2 logical-root canonicalization only after authoritative
   same-directory resolution, including symlink/junction escape Local fallback where
   supported;
5. successful canonical open recording;
6. Jobs logical-locator preservation;
7. Recent identity mismatch preserving the last valid Result and history;
8. valid Result browsing with unavailable native sources;
9. Provenance publication metadata and live root-mapping freshness;
10. delayed logical Recent A resolution followed by newer File B and Jobs B, proving A
    cannot start a later open and history/Provenance remain on B;
11. close/recreate history persistence;
12. existing P5-B/P5-C/P5-D regressions in the full repository validation.

P5-F may extend stress/performance coverage but must not redefine these correctness
contracts.

## 10. Owner Windows manual validation — required before merge

P5-E remains Active until the owner validates the exact PR head on Windows.

### A. Recent / MRU / Clear

- Open multiple Results from **File > Open IQA Result...**.
- Open a terminal Result from Remote IQA **Jobs**.
- Confirm **Open Recent IQA Results** is max 10, MRU ordered, and duplicate locators move
  to the front rather than duplicate.
- Reopen an entry and confirm it moves to MRU.
- Clear Recent IQA Results and confirm Images/Folders/Sessions Recent remain unchanged.

### B. Logical-root remap

- Record a production logical Result.
- Change the same `storage_root_id` to another valid client mapping containing the same
  Result.
- Reopen from Recent and confirm the new mapping is used.
- Change mapping while a reopen is in flight and confirm stale mapped-path work cannot
  replace the current Result.
- With a Scene still selected, add/remove its source root mapping and confirm Provenance
  and P5-D Inspect availability refresh immediately without Result reopen or Scene
  reselection.

### C. Offline / missing / replacement

- Make the result root unavailable and confirm the Recent entry is kept unless Remove is
  explicitly chosen.
- Restore availability and confirm reopen succeeds.
- Replace the locator target with another Result identity and confirm the reopen is
  rejected while the previously valid Result remains displayed.

### D. Result-only / native source failure

- Open a valid Result whose Scene sources are offline/unmapped/missing.
- Confirm Overview/Scene Trend/Provenance remain browseable.
- Confirm **Inspect in Viewer** reports source verification unavailability/failure without
  marking the Result corrupt.

### E. Provenance / v1 / PARTIAL

- Confirm schema-v2 Result/Scene/source provenance matches the published manifest.
- Confirm source SHA-256 and dimensions are visible.
- Open a schema-v1 fixture and confirm explicit historical/read-only treatment with no
  synthetic v2 fields.
- Open a PARTIAL Result and confirm successful Scenes and failed/cancelled diagnostics are
  preserved.

### F. Lifecycle / P5-D teardown

- Inspect a Scene, then open another Result from File, Jobs, and Recent paths.
- Confirm previous Inspect/spatial state cannot overwrite the new Result.
- Start resolving a logical Recent A, then before it resolves open newer File B; release
  A and confirm B remains current and A is not recorded or presented.
- Repeat the delayed logical Recent A case with newer Jobs B and confirm the same latest
  intent behavior.
- Exercise rapid already-resolved A→B canonical opens and confirm only B can become
  current.
- Close PixelScope during historical resolution/open and recreate the window; confirm no
  stale callback or duplicate controller remains.

### G. Local-workspace authority

- Browse and reopen Results without Inspect.
- Confirm Files, Selected, Current Comparison Page, source residency, Difference, ROI,
  Line Profile, and local Primary are unchanged.
- Confirm IQA Reference remains independent from local Primary.

Record exact-head results in PR #44. Do not infer PASS from P5-D or an earlier P5-E head.

## 11. Validation evidence during Draft review

Owner Windows automated/static validation was reported PASS on earlier Draft head
`dd1ebfb8aa4846233de854fcd3cb313f069161e9`, including the full `pytest -q` suite,
Ruff lint/format, mypy, docs checker, pip check, and `git diff --check`.

Independent whole-PR review then identified additional P5-E lifecycle, live Provenance,
manual-locator canonicalization, and documentation-scope findings. Those fixes move the
PR head, so the earlier PASS is historical evidence only. **The post-review exact head
must be revalidated before merge**, followed by owner manual validation A–G and
independent re-review.
