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

1. parse and semantically validate Session metadata;
2. probe Registered source paths without decoding them;
3. if zero Registered sources are loadable, leave the current workspace unchanged and report the condition;
4. reconcile Registered documents, reusing already-registered matching paths where possible and removing current Registered entries that are outside the saved Session;
5. restore resolved RAW reconstruction metadata without prompting when valid metadata is already saved;
6. restore the loadable saved Selected subset in saved order;
7. derive Current Comparison Page from Selected + saved Active under the existing P3 page policy;
8. restore layout and applicable Primary;
9. restore saved Active as a distinct state from Primary;
10. restore Display Gain and applicable Split state;
11. defer ROI/Line restoration until the relevant foreground sources are ready;
12. if a saved Difference recipe is applicable, wait until both recipe sources are ready, then invoke the existing asynchronous Difference calculation path.

The loader must not synchronously decode all Registered sources. `Registered → Selected → Current Comparison Page → Presented → Resident when required` remains authoritative, and **Analysis Working Set = Current Comparison Page** remains unchanged.

## UI responsiveness / freeze prevention

Opening a large Session must not convert registration into eager decode.

- Registered-only sources are registered as metadata/pending documents and do not become foreground load requirements merely because they are in the Session.
- Foreground source work remains bounded to the Current Comparison Page and correctness dependencies.
- repeated Session restoration must not intentionally issue duplicate foreground load work for the same source.
- unresolved RAW remains lazy and uses the established foreground profile-resolution/decode path when no saved valid profile is available.
- Difference is restored as recipe intent and recalculated only through the existing asynchronous Difference pipeline after both sources are ready.

Session loading therefore performs lightweight artifact/path/state reconstruction synchronously while heavy image decode and Difference computation stay in the existing worker lifecycle.

## Missing and unusable Session sources

- partial source availability restores the loadable Registered/Selected subset and reports missing sources;
- a missing Selected member is omitted from the restored Selected subset;
- saved Active falls back through the existing Selected policy if unavailable;
- saved Primary is restored only when applicable to the derived Current Comparison Page;
- missing Difference recipe source(s) do not cause arbitrary source substitution; Difference restoration is skipped/left unavailable;
- zero loadable Registered sources leaves the pre-open workspace and P4-A curation unchanged;
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
- Registered-all versus Selected-subset semantics;
- Active and Primary restored independently;
- large Session open bounded to Current Comparison Page foreground requirements;
- no Registered-only eager decode;
- resolved/unresolved RAW restore behavior;
- ROI/Line/Display Gain/Split state restoration;
- Difference recipe persistence with lazy asynchronous recalculation and no Difference cache persistence;
- partial and zero-loadable source behavior;
- typed Recent MRU, missing Remove/Keep, wrong-kind protection, restart persistence, clear/privacy behavior, and observer failure isolation.

Owner-reported Windows focused validation on the contract-revision head is green for the Session/Recent/P4-B compatibility suite, `ruff check .`, and `mypy src`. Full repository validation and Ruff-format baseline closure remain separate merge gates unless subsequently recorded as passed.
