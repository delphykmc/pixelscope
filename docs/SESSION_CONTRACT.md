# PixelScope Session v1 contract

Status: Authoritative from P4-C owner contract revision (2026-08-12)

This document supersedes the product/runtime meaning of the P4-B Comparison Set artifact while preserving P4-B as historical implementation context and read compatibility. New UI, new `.pixelscope` writes, Recent history, and subsequent P4 work use **Session** terminology and the contract below.

## Product intent

A PixelScope Session is a durable representation of **user-authored workspace intent**, not a process snapshot and not a serialization of runtime caches.

A Session lets a user reopen PixelScope and continue substantially the same analysis workspace without forcing all registered sources to decode during file-open.

## File and schema

- extension: `.pixelscope`
- encoding: UTF-8 JSON
- new writer kind: `pixelscope-session`
- schema version: `1`
- persistent source identity: normalized absolute local source path
- old `pixelscope-comparison-set` v1 artifacts remain read-compatible only
- no fuzzy relocation or automatic source repair
- save remains atomic through same-directory temporary file, flush/fsync, and replace
- one logical Session open reads/parses the artifact exactly once and carries the same validated immutable Session object through the full restore transaction
- primitive Session fields are validated strictly; unsupported numeric/string coercions are rejected rather than normalized silently

## Durable Session state

Session v1 stores:

- all persistent **Registered** source paths, in registration order;
- resolved RAW profile metadata when required to reconstruct a RAW source;
- ordered logical **Selected** paths;
- saved **Active** path when applicable;
- saved **Primary** path when applicable;
- stable layout mode;
- shared ROI bounds;
- shared Line selection;
- Display Gain;
- Split Channels state;
- a regenerable Difference recipe when Difference is currently represented.

The Difference recipe stores intent only:

- source A path;
- source B path;
- channel;
- Absolute/Mask mode;
- threshold;
- Difference gain;
- analysis region.

Saved Difference A/B are distinct Selected Session members. They may be outside the restored Current Comparison Page; in that case they are at most two additional feature-owned correctness dependencies rather than a new Selected-wide load authority.

## Explicitly non-persistent runtime state

Session v1 does **not** serialize:

- decoded native arrays;
- source residency/LRU/protection state;
- preview or Qt texture buffers;
- preload plans/workers;
- foreground workers, request tokens, generations, or task objects;
- Difference maps, cache entries, metrics, or worker results;
- Statistics/Histogram/Line Profile calculated results;
- transient Split/Difference derived `ImageDocument`s;
- P4-A temporary review baseline or Pick Set;
- other reproducible cache/derived process state.

This separation is a correctness and performance boundary: Session persists intent; existing runtime authorities regenerate resources when required.

## Open and restore sequence

Session open validates the artifact before mutating the workspace. For valid input the intended sequence is:

1. parse and semantically validate Session metadata exactly once;
2. probe Registered source paths without decoding them;
3. stage loadable Registered identities without deleting the current workspace;
4. if no incoming source can be registered, leave the current workspace and P4-A curation unchanged and report the unavailable sources;
5. after at least one incoming source has a stable identity, reconcile Registered documents, reusing already-registered matching paths where possible and removing current Registered entries that are outside the saved Session;
6. restore resolved RAW reconstruction metadata without prompting when valid metadata is already saved;
7. restore the loadable saved Selected subset in saved order;
8. derive Current Comparison Page from Selected + saved Active under the existing P3 page policy;
9. restore layout and applicable Primary;
10. restore saved Active as a distinct state from Primary;
11. restore Display Gain and applicable Split state;
12. establish Current Comparison Page foreground loads plus at most two saved Difference correctness dependencies;
13. wait until the Current Comparison Page foreground batch reaches a stable terminal state before restoring ROI/Line analysis intent;
14. restore ROI and Line state against the settled ready Current Comparison Page sources;
15. if a saved Difference recipe is applicable, wait until both recipe sources are ready, validate the saved channel/options against the reconstructed pair, then invoke the existing asynchronous Difference calculation path;
16. keep the Session restore busy transaction active until the final Difference presentation, layout, and Display Gain presentation state have settled.

The loader must not synchronously decode all Registered sources. `Registered → Selected → Current Comparison Page → Presented → Resident when required` remains authoritative, and **Analysis Working Set = Current Comparison Page** remains unchanged.

## Foreground completion and self-healing boundary

Session restore must not add a second foreground-load ownership system. It reuses MainWindow's native `_ensure_loaded()` state machine, where `pending → loading` already provides idempotent worker admission.

Session must therefore **not** permanently remember that a source was requested once and suppress later `_ensure_loaded()` calls. During Session restore, normal render/navigation/preload reconciliation can invalidate or cancel an in-flight foreground request and return the document to `pending`. The deferred Session completion barrier must reissue `_ensure_loaded()` for such pending Current Comparison Page or Difference dependency sources so the restore can recover instead of leaving a permanent loading placeholder.

ROI, Line, and Difference reconstruction are deferred until the Current Comparison Page foreground batch is settled. This prevents analysis/presentation restoration from racing the source-load batch and avoids layering Statistics/Line/Difference work onto a page whose source identities are still transitioning through pending/loading states.

A settled Current Comparison Page source is one of:

- decoded and ready;
- explicit load error;
- unresolved RAW whose profile prompt was explicitly suppressed/cancelled.

The completion barrier itself remains lightweight and event-loop driven; it does not decode images, busy-wait, or calculate Difference synchronously.

## UI responsiveness / freeze prevention

Opening a large Session must not convert registration into eager decode.

- Registered-only sources are registered as metadata/pending documents and do not become foreground load requirements merely because they are in the Session.
- Foreground source work remains bounded to the Current Comparison Page and correctness dependencies.
- native `_ensure_loaded()` idempotency, not a Session-local one-shot request cache, controls duplicate worker admission.
- pending foreground work returned by cancellation/token invalidation is eligible for a Session-barrier retry.
- unresolved RAW remains lazy and uses the established foreground profile-resolution/decode path when no saved valid profile is available.
- ROI/Line analysis restoration begins only after the Current Comparison Page foreground batch settles.
- Difference is restored as recipe intent and recalculated only through the existing asynchronous Difference pipeline after both sources are ready.
- incompatible saved Difference channel/options are not silently substituted; Difference restoration is skipped with compact feedback.

Session loading therefore performs lightweight artifact/path/state reconstruction synchronously while heavy image decode, display-gain rendering, analysis, and Difference computation stay in the existing worker lifecycles.

## Session restore busy transaction

`Open Session` is one compound user command even though it delegates heavy work to several asynchronous runtime authorities. After artifact validation succeeds and restore begins, PixelScope therefore owns an **application-modal Session restore transaction** until the saved workspace reaches its final presentable state.

The busy transaction:

- blocks user interaction with PixelScope workspace controls while restore is in flight;
- does **not** block the Qt event loop, wait synchronously for workers, or use a nested `exec()` loop;
- keeps image-load, Difference, and Display Gain workers running normally;
- reports the current phase rather than presenting intermediate reconstructed views as user-ready state;
- uses determinate progress for the Current Comparison Page load count where the total is known;
- uses an indeterminate progress state for operations such as Difference recalculation whose completion percentage is not meaningful;
- remains active through final Difference presentation and Display Gain settling, not merely until source registration or source decode completes;
- releases the input gate after the final presentation is ready, or after a bounded display-presentation settle timeout so a failed viewer-only preview cannot permanently lock the application.

The user-facing phase sequence is conceptually:

1. Registering sources;
2. Loading selected images (`n / total`);
3. Restoring ROI and Line Profile;
4. loading saved Difference dependencies when required;
5. Recalculating Difference when required;
6. Applying display state;
7. Session restored.

Session restore v1 intentionally has no Cancel command. Correct Cancel semantics require a defined rollback of the pre-open Registered/Selected/presentation workspace, which is outside the P4-C contract. The modal input gate applies only to the compound Session Open workflow; ordinary user-initiated Difference calculations, Display Gain changes, preload, and normal analysis remain interactive under their existing contracts.

## Missing and unusable Session sources

- partial source availability restores the loadable Registered/Selected subset and reports missing or registration-failed sources;
- a missing Selected member is omitted from the restored Selected subset;
- saved Active falls back through the existing Selected policy if unavailable;
- saved Primary is restored only when applicable to the derived Current Comparison Page;
- missing Difference recipe source(s) do not cause arbitrary source substitution; Difference restoration is skipped/left unavailable;
- zero successfully registered incoming sources leaves the pre-open workspace and P4-A curation unchanged;
- no fuzzy relocation is performed.

## Recent entry contract

`File` exposes one Open group followed by Save Session:

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

Other existing File commands may follow in later groups.

Recent history is a bounded typed MRU of user entry paths:

- Images: successful direct image-open paths;
- Folders: successful folder-registration paths;
- Sessions: successfully saved/opened `.pixelscope` Session paths.

Each type keeps at most ten normalized absolute paths. New persistence uses:

- `recent/images`
- `recent/folders`
- `recent/sessions`

The old draft `recent/comparison_sets` key may be consumed for migration/read compatibility but is not the new authoritative name.

Recent is best-effort observational metadata. It owns no selection, source, residency, preload, Difference, analysis, or curation state. Missing entries use explicit Remove/Keep behavior; existing-but-unusable or wrong-resource-kind paths remain history unless the user removes them.

Recent keys remain outside `ApplicationSettings` schema v5 and outside Reset Settings. Clear Recent Entries is the explicit privacy/history removal command. Absolute paths may disclose local filesystem layout.

## Compatibility boundary

P4-B Comparison Set remains historical context, not the current product concept.

- existing `pixelscope-comparison-set` v1 artifacts may be opened as Sessions;
- legacy internal controller/test aliases may remain temporarily to preserve regression coverage;
- new UI must say Session;
- new artifacts must write `pixelscope-session`;
- new Recent UI/key semantics must say Session;
- future P4 work should extend Session rather than reintroduce Comparison Set as a parallel user concept.

## Validation gates

P4-C Session closure requires coverage for:

- Session schema roundtrip and legacy P4-B read compatibility;
- single-read transactional restore;
- strict primitive/schema validation with no pre-mutation side effects;
- Registered-all versus Selected-subset semantics;
- Active and Primary restored independently;
- large Session open bounded to Current Comparison Page foreground requirements;
- no Registered-only eager decode;
- non-destructive zero-registration behavior;
- resolved/unresolved RAW restore behavior;
- ROI/Line/Display Gain/Split state restoration;
- Current Comparison Page foreground completion before analysis-intent restoration;
- recovery when a Session foreground source returns to `pending` during restore;
- Difference recipe persistence with lazy asynchronous recalculation and no Difference cache persistence;
- off-page Difference pair bounded to at most two additional correctness dependencies;
- incompatible saved Difference channel/options skip rather than substitute;
- a real-worker integration path covering four Selected sources + Difference + ROI + Line + non-1× Display Gain reopening without a stuck loading presentation;
- application-modal Session restore feedback present from restore start through final presentation, with no nested event loop and automatic release at completion;
- partial and zero-loadable source behavior;
- typed Recent MRU, missing Remove/Keep, wrong-kind protection, restart persistence, clear/privacy behavior, and observer failure isolation.

Owner-reported Windows validation before the foreground-completion follow-up was green. The owner then reproduced a real Session reopen stall with four Selected sources plus Difference, ROI, Line, and 2× Display Gain. The timer-only deferred restore fix subsequently passed the owner's manual reproduction. The new application-modal restore-progress/input-gate follow-up requires fresh owner validation before merge.
