# PixelScope Session v1 contract

Status: Authoritative P4-C contract, reconciled with merged PR #32 and PR #33

This document supersedes earlier P4-C planning text that limited the phase to
Comparison Set entry UX. P4-B remains historical implementation/read-compatibility
context; the current product concept is **PixelScope Session**.

## Product intent

A Session persists **user-authored workspace intent**, not a process snapshot.
Reopening a Session should reconstruct the same practical analysis workspace while
letting the existing P2/P3/P4 runtime owners regenerate decoded/derived state.

## File and compatibility boundary

- extension: `.pixelscope`;
- encoding: UTF-8 JSON;
- new writer kind: `pixelscope-session`;
- schema version: `1`;
- persistent source identity: normalized absolute local source path;
- legacy `pixelscope-comparison-set` v1 artifacts remain read-compatible;
- legacy Comparison Set maps `Registered = sources` and `Selected = sources`;
- no fuzzy relocation or automatic path repair;
- save remains atomic through same-directory temporary file, flush/fsync, and replace;
- one logical open parses/validates the artifact exactly once;
- malformed primitive fields are rejected rather than silently coerced.

New UI, new writes, Recent history, and subsequent P4 work use **Session** terminology.

## Durable Session state

Session v1 stores:

- all persistent **Registered** source paths in registration order;
- resolved RAW profile metadata needed to reconstruct a saved RAW source;
- ordered logical **Selected** paths;
- saved **Active** path when applicable;
- saved **Primary** path when applicable;
- stable layout mode;
- shared ROI bounds;
- shared Line selection;
- Display Gain;
- Split Channels state;
- a regenerable Difference recipe when an active Difference binding exists.

The Difference recipe contains only intent:

- source A path;
- source B path;
- channel;
- Absolute/Mask mode;
- threshold;
- Difference gain;
- Full image/Active ROI region.

Difference A/B must be distinct Selected Session members. They may be off the
restored Current Comparison Page; this creates at most two feature-owned correctness
dependencies, not a Selected-wide load/residency authority.

## Explicitly non-persistent state

Session v1 does **not** serialize:

- decoded native arrays;
- source residency/LRU/protection bookkeeping;
- preview/Qt texture buffers;
- preload plans or workers;
- foreground workers, tokens, generations, or task objects;
- Difference maps/cache entries/metrics/results;
- Statistics/Histogram/Line calculated results;
- transient Split/Difference `ImageDocument`s;
- P4-A temporary baseline/Pick Set;
- other reproducible runtime/derived buffers.

`Registered → Selected → Current Comparison Page → Presented → Resident when required`
and `Analysis Working Set = Current Comparison Page` remain authoritative.

## Open transaction

For a valid Session, the restore sequence is:

1. read/parse/semantically validate the artifact exactly once;
2. probe Registered source paths without decoding them;
3. stage incoming registration identities with existing registration APIs;
4. if zero incoming sources actually register, keep the existing workspace/Picks
   unchanged and report the unavailable sources;
5. after the registration commit boundary, teardown any pre-existing active
   Difference through the merged PR #33 lifecycle;
6. clear temporary P4-A curation state and reconcile Registered membership to the
   saved Session;
7. restore saved RAW reconstruction metadata;
8. restore loadable Selected in saved order;
9. derive Current Comparison Page from Selected + saved Active;
10. restore layout, applicable Primary, and Active independently;
11. restore Display Gain and applicable Split state;
12. foreground-load Current Comparison Page plus at most the saved Difference A/B
    correctness dependencies;
13. wait for Current Comparison Page foreground work to settle before replaying
    ROI/Line analysis intent;
14. restore ROI and Line;
15. when saved Difference A/B are ready, validate exact saved options and replay the
    recipe through one explicit Difference **Calculate** request.

The loader never eagerly decodes every Registered source.

## PR #32 / #33 authority

Session restore consumes the merged runtime contracts; it does not redefine them.

### PR #32

PR #32 remains authoritative for:

- Display Gain worker/concurrency policy;
- heavy Statistics/Difference analysis pool ownership;
- retained viewer/source identity across presentation changes;
- asynchronous Difference preview rendering and stale-result rejection;
- six-source Difference presentation behavior.

P4-C adds no generic Display Gain, Difference worker, or Multi View fix.

### PR #33

PR #33 remains authoritative for active Difference lifecycle:

- Difference is a derived presentation;
- only successful explicit **Calculate** establishes an active Difference result and
  its A/B provenance;
- toolbar **Diff** is visibility-only for that established result;
- toolbar toggling never infers another pair or starts implicit calculation;
- Selected/Keep mutation follows the merged teardown rules;
- generation-keyed Difference cache remains feature-owned and independent.

Therefore a saved Session recipe **must not pre-populate
`MainWindow._difference_source_ids` or otherwise impersonate an active result**.
During restore, saved A/B are only pending correctness dependencies. Once both are
ready, Session binds the explicit DifferencePanel pair/options and invokes
`calculate_difference()`. The normal PR #33 result-ready path alone establishes the
active Difference document/provenance and toolbar visibility state.

If a saved channel/mode/region/threshold is incompatible with the reconstructed pair,
Difference restore is skipped with compact feedback. No channel, pair, or option is
silently substituted.

## Foreground completion and self-healing

Session restore reuses MainWindow's native `_ensure_loaded()` state machine. It must
not maintain a permanent one-shot request cache of its own.

If ordinary navigation/render/token reconciliation returns a required source to
`pending`, the Session completion loop may request that source again. The completion
loop is event-loop/timer driven; it does not decode, busy-wait, or synchronously
calculate Difference.

A Current Comparison Page member is settled when it is:

- decoded/ready;
- in explicit load error;
- unresolved RAW whose foreground profile prompt was explicitly cancelled/suppressed.

ROI/Line/Difference reconstruction waits for the applicable source boundary instead
of re-entering synchronous viewer render callbacks.

## Missing/unusable sources

- partial availability restores the loadable Registered/Selected subset and reports
  unavailable paths;
- a missing Selected member is omitted from restored Selected;
- unavailable Active falls back through existing Selected policy;
- Primary restores only when applicable to the derived page;
- missing/incompatible Difference sources/options do not trigger substitution;
- zero successful incoming registrations leave the pre-open workspace/Picks intact;
- no fuzzy relocation is performed.

## Recent entry contract

File entry UX is:

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

Recent is a bounded typed MRU of path-only entry history:

- Images: successful direct image-open paths;
- Folders: successful folder-registration paths;
- Sessions: successfully opened/saved `.pixelscope` Session paths.

Each type keeps at most 10 normalized absolute paths. Authoritative keys are:

- `recent/images`;
- `recent/folders`;
- `recent/sessions`.

Legacy `recent/comparison_sets` may be consumed only as migration/read fallback.
Recent history remains outside ApplicationSettings schema v5 and Reset Settings.
Each typed submenu owns its own clear command.

Missing entries use explicit **Remove / Keep**. Wrong filesystem kind and existing
invalid Session artifacts remain history unless explicitly removed. Recent
bookkeeping is best-effort observer metadata: QSettings/history failure cannot turn
a successful canonical Image/Folder/Session workflow into failure.

Recent owns no source, selection, curation, residency, preload, Difference, analysis,
or Current Comparison Page authority. Absolute paths may disclose local filesystem
layout.

## Validation gates

P4-C closure requires fresh validation on the #32/#33-based head for:

- Session schema roundtrip and legacy P4-B read compatibility;
- strict malformed-schema rejection with no runtime mutation;
- exactly-one-read open transaction;
- Registered-all versus Selected-subset semantics;
- Active/Primary/layout independence;
- zero-registration non-destructive behavior;
- no Registered-only eager decode;
- resolved/unresolved RAW restore behavior;
- ROI/Line/Display Gain/Split restoration;
- Difference recipe replay through PR #33 explicit Calculate, without provenance
  pre-binding;
- off-page Difference dependency bounded to at most two extra sources;
- incompatible saved Difference options skip rather than substitute;
- real-worker four-source + ROI + Line + non-1× Gain + Difference reopen to final
  Difference presentation;
- typed Recent MRU, migration, Remove/Keep, wrong-kind protection, restart
  persistence, per-type clear, and observer failure isolation;
- inherited PR #32/#33 Difference/Display Gain lifecycle regressions.

Validation from the abandoned pre-rebase/freeze-debug heads is historical only. No
PASS is inferred for the current rebuilt head until owner-local validation is
reported.
