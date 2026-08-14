# PixelScope Session v1 contract

Status: Authoritative P4-C contract, reconciled with merged PR #32 and PR #33

This document supersedes earlier P4-C planning text that limited the phase to
Comparison Set entry UX. P4-B remains historical implementation/read-compatibility
context; the current product concept is **PixelScope Session**.

## Product intent

A Session persists enough durable **user-authored workspace intent** to reproduce the
practical workspace that existed at Save time. It is not a process snapshot.

Restore reconstructs that intent through the existing P2/P3/P4 loading, residency,
Difference, viewer, and presentation pipelines. Session must not create parallel
runtime authority merely to reproduce saved state.

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

- persistent **Registered membership** as source paths;
- resolved RAW profile metadata needed to reconstruct a saved RAW source;
- ordered logical **Selected** paths;
- a stable source-path **Current Comparison Page anchor**;
- saved source **Active** path when applicable;
- saved **Primary** path when applicable;
- stable layout mode;
- shared ROI bounds;
- shared Line selection;
- Display Gain;
- Split Channels state;
- a regenerable Difference recipe when an active Difference binding exists.

### Ordering semantics

Registered insertion/registration order is **not** durable Session state. Reopening a
Session restores Registered membership; the Files tree keeps its existing grouping and
presentation-order policy. Session does not add a new global Files ordering rule.

Selected order **is** durable because it defines Current Comparison Page membership,
navigation, and presentation. For the loadable subset, saved Selected order is
preserved exactly.

### Current Comparison Page identity

Current Comparison Page is still derived runtime state rather than a duplicated saved
collection, but Session persists one Selected source-path anchor so the same page can
be reconstructed independently of source Active state.

This matters when the saved Active presentation is generated Difference. A generated
Difference document has no durable source `active_path`; the page anchor still returns
the workspace to the page on which that Difference was calculated.

For older Session artifacts without an explicit anchor, the model derives a compatible
anchor from durable state in this order: Primary, source Active, Difference source A,
then first Selected source.

## Difference recipe

The Difference recipe contains intent only:

- source A path;
- source B path;
- channel;
- Absolute/Mask mode;
- threshold;
- Difference gain;
- Full image/Active ROI region.

Difference A/B must be distinct Selected Session members. A normally saved recipe is
Current-Comparison-Page scoped because Difference calculation itself is page scoped.
Session therefore restores the saved page first and then replays the recipe through
the normal current-page Difference controls. It does **not** create special off-page
Difference loading/residency ownership.

## Explicitly non-persistent state

Session v1 does **not** serialize:

- decoded native arrays;
- source residency/LRU/protection bookkeeping;
- preview/Qt texture buffers;
- preload plans or workers;
- foreground workers, tokens, generations, or task objects;
- Difference maps/cache entries/metrics/results;
- generated Difference documents;
- Statistics/Histogram/Line calculated results;
- transient Split `ImageDocument`s;
- P4-A temporary baseline/Pick Set;
- other reproducible runtime/derived buffers.

`Registered → Selected → Current Comparison Page → Presented → Resident when required`
and `Analysis Working Set = Current Comparison Page` remain authoritative.

## Open transaction

For a valid Session, restore proceeds in this order:

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
9. reconstruct the saved Current Comparison Page from the saved page anchor and
   Selected order;
10. restore layout and establish applicable Primary/source Active for the reconstructed
    workspace;
11. foreground-load the Current Comparison Page through the existing MainWindow load
    pipeline;
12. restore Display Gain and applicable Split state after the page reaches terminal
    source state;
13. wait for applicable Display Gain previews to settle;
14. restore applicable ROI and Line state;
15. if the saved Difference recipe remains applicable to the restored current page,
    bind its exact A/B/options through DifferencePanel and issue exactly one explicit
    **Calculate** request;
16. let the merged PR #33 result-ready path alone establish active Difference
    provenance/document/toolbar state;
17. re-apply saved source Primary and Active as the final presentation commit.

Primary/Active are therefore established twice by design: once synchronously when the
workspace is reconstructed so canonical P4-B open semantics remain immediately true,
and once after asynchronous display/Difference work so transient presentation changes
cannot become the final restored state.

The loader never eagerly decodes every Registered source.

## Session restore progress UX

Session Open exposes the asynchronous reconstruction transaction through a
**MainWindow-owned child overlay**, not a `QDialog`, not `ApplicationModal`, and never
enters a nested event loop.

The restore state machine always follows the same maximum eight-step procedure:

1. **Reading Session**;
2. **Restoring sources**;
3. **Restoring workspace**;
4. **Loading current page**;
5. **Restoring display**;
6. **Restoring analysis**;
7. **Rebuilding Difference**;
8. **Finalizing workspace**.

The compact overlay does **not** list all eight rows simultaneously. It shows the
procedure progress bar, the current `Step n of 8` title, and current-step detail only.
This keeps the overlay small while still making background viewer reconstruction
explicit to the user.

The progress bar represents **procedure completion**, not elapsed-time or ETA
prediction. A long-running step exposes concrete local detail where available, for
example `3 / 6 images ready` during current-page loading or Display Gain preview
completion state. Optional state such as Split Channels, ROI, Line, or Difference is
not artificially delayed: an inapplicable step completes immediately and the
procedure advances.

While the overlay is visible it acts as a window-local input shield so toolbar/menu,
selection, navigation, and analysis gestures cannot race the restore transaction.
The Qt event loop, source workers, Display Gain workers, and Difference workers remain
active. The overlay owns no source, selection, residency, worker, Difference, or
presentation authority; it only observes and reports the canonical restore state.
Progress-update failure must not turn an otherwise successful Session restore into a
failure.

There is no restore **Cancel** command in Session v1. Adding Cancel would require an
explicit partial-restore rollback transaction and is outside the current contract.
There is also no artificial completion delay: after Step 8 commits saved
Primary/Active, the overlay may disappear on the normal event-loop progression.

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
Session restores the saved Current Comparison Page, binds the saved A/B pair through
that page's normal DifferencePanel controls, restores exact compatible options, and
calls `calculate_difference()` once. The normal PR #33 result-ready path alone
establishes active Difference provenance and visibility state.

If the saved pair is no longer on the restored page, a source is unavailable, or a
saved channel/mode/region/threshold is incompatible with the reconstructed pair,
Difference restore terminates with compact feedback. No pair, channel, page, or
option is silently substituted.

## Foreground completion and terminal analysis behavior

Session restore reuses MainWindow's native `_ensure_loaded()` state machine. It must
not maintain a permanent one-shot request cache of its own.

If ordinary navigation/render/token reconciliation returns a required current-page
source to `pending`, the Session completion loop may request that same page source
again. The loop is event-loop/timer driven; it does not decode, busy-wait, or
synchronously calculate Difference.

A Current Comparison Page member is settled when it is:

- decoded/ready;
- in explicit load error;
- unresolved RAW whose foreground profile prompt was explicitly cancelled/suppressed.

ROI/Line/Difference reconstruction begins only after the whole page is settled. If the
settled page has no usable source for saved ROI/Line intent, those derived states are
skipped and their pending state is cleared. An `Active ROI` Difference whose ROI
cannot be restored is also skipped. These are terminal outcomes: Session must not keep
rescheduling a completion timer indefinitely for analysis state that cannot become
applicable.

## Missing/unusable sources

- partial availability restores the loadable Registered/Selected subset and reports
  unavailable paths;
- a missing Selected member is omitted from restored Selected while remaining
  Selected order is preserved;
- if the saved page anchor is unavailable, restore falls back deterministically to an
  available saved source Active or first loadable Selected member;
- source Active restores only when applicable to the reconstructed page;
- Primary restores only when applicable to the reconstructed page;
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
- Registered membership versus ordered Selected semantics;
- page-anchor persistence and same-page Save→Open with more than six Selected;
- generated-Difference Active Save→Open returning to the same later page;
- Active/Primary/layout independence within the restored page;
- zero-registration non-destructive behavior;
- no Registered-only eager decode;
- resolved/unresolved RAW restore behavior;
- ROI/Line/Display Gain/Split restoration;
- terminal skip when settled page analysis state is unusable;
- Difference recipe replay through current-page controls and PR #33 explicit
  Calculate, without provenance pre-binding;
- incompatible saved Difference pair/options skip rather than substitute;
- real-worker four-source + ROI + Line + non-1× Gain + Difference reopen to final
  Difference presentation;
- compact MainWindow-owned restore overlay through full eight-step reconstruction;
- typed Recent MRU, migration, Remove/Keep, wrong-kind protection, restart
  persistence, per-type clear, and observer failure isolation;
- inherited PR #32/#33 Difference/Display Gain lifecycle regressions.

Validation from abandoned pre-rebase/freeze-debug heads is historical only. No PASS
is inferred for the current rebuilt head until owner-local validation is reported.
