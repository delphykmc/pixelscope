# PixelScope architecture

## Runtime ownership hierarchy

PixelScope keeps logical workflow state separate from decoded-source lifecycle:

```text
Registered
    ↓ user selection
Selected
    ↓ ordered page derivation
Current Comparison Page        # max 6
    ↓ presentation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

`MainWindow` remains the runtime orchestration authority for Registered/Selected,
page position, Active/Primary intent, layout, loading, source residency integration,
preload integration, and analysis/presentation coordination.

Selected may contain more than six sources. The Current Comparison Page is derived
from Selected ordering and current navigation position. It is not a separately owned
document collection and is not persistence authority.

## Source and resource boundaries

Native decoded `ImageDocument.source` remains the numerical authority for analysis.
Presentation previews, gained previews, Difference presentation, and Split views are
derived/transient representations.

Source residency is byte-budgeted using exact native `source.nbytes`. Generic
protection is limited to the Current Comparison Page and explicit correctness
dependencies such as visible/active documents, foreground load ownership, promoted
preload, and Difference dependencies. Selected alone is not protection authority.

P2 preload remains Folder Position `+1`, exactly one position ahead, with max-one
speculative worker. Comparison Page navigation and P4 workflow membership do not
create another preload owner.

Difference cache is independent of source residency. Runtime diagnostics are bounded,
sanitized, and observation-only.

## Input and RAW boundary

The normal registration path owns source-path to runtime-document identity reuse.
Open Images/direct image D&D is selection-oriented; Open Folder/folder D&D is
registration-oriented.

RAW source registration may remain pending. Deterministic profile resolution is
performed according to P3-D semantics when foreground native source is required.
Resolved `RawProfile` data is validated by the existing `RawProfile` model. No profile
inference or global profile database is introduced by P4.

## P4-A temporary curation

`core.review_selection.ReviewSelectionState` is an ID-only temporary state model.
`ui.review_selection.ReviewSelectionController` owns the Pick workflow and delegates
Keep Selection to the inherited Selected mutation path.

Pick state owns no source arrays, workers, caches, residency, preload, or analysis.
The Pick Set and captured baseline are not persistent.

## P4-B Comparison Set persistence

P4-B adds a separate external-artifact boundary rather than a full application-session
serializer.

```text
.pixelscope Comparison Set artifact
        ↓
core.comparison_set.ComparisonSet
        ↓
io.comparison_set_repository.ComparisonSetRepository
        ↓
ui.comparison_set.ComparisonSetController
        ↓
normal registration / Selected mutation / Active / Primary / layout APIs
        ↓
Current Comparison Page derived normally
```

### Domain/schema

`ComparisonSet` is Qt-free. v1 contains:

- `kind = pixelscope-comparison-set`;
- `schema_version = 1`;
- ordered `ComparisonSetSource` entries using normalized absolute local paths;
- optional Active path;
- optional Primary path;
- `Auto`, `Single View`, or `Multi View` layout mode;
- optional already-resolved RawProfile payload per RAW source.

Runtime `document_id` is never persistent identity.

Duplicate source-path identities are rejected so Selected ordering and member identity
remain deterministic.

### Repository/codec

`ComparisonSetRepository` owns JSON parsing/validation and atomic persistence. It
validates a supported schema before the controller mutates runtime state. Future
schema versions are rejected rather than guessed or rewritten.

Writes use a same-directory temporary file, flush/fsync, and atomic replacement so a
failed save does not intentionally publish a partial artifact as valid state.

Same-version unknown fields are ignored on read; required fields and known field types
remain strict. RawProfile payloads are validated through the existing model before
use.

### UI orchestration

`ComparisonSetController` adds **Open Comparison Set...** and **Save Comparison
Set...** under File. It is installed after P4-A review-selection composition so a
Comparison Set open calls the current wrapped `_select_document_ids` boundary. This
means P4-A temporary curation invalidates through the already-established Selected
mutation contract rather than through a second lifecycle.

Save reads only current logical Selected and stable Active/Primary/layout intent. It
does not call `_ensure_loaded()` and does not clear temporary Picks.

Open first validates and preflights saved paths. Loadable members are registered or
reused without RAW profile prompts at registration. Saved resolved profiles are
associated before Selected is replaced. The existing Selected/render path then loads
only the derived foreground Current Comparison Page as required.

Existing Registered non-set members remain Registered. Missing artifact members are
skipped in saved order. Zero-loadable and invalid artifacts leave the existing
workspace unchanged.

### Non-ownership

The Comparison Set domain/repository/controller is **not**:

- a decoded-source owner;
- a residency/LRU/protection owner;
- a preload owner;
- a worker pool;
- a cache owner;
- an analysis working-set owner;
- an independent page owner;
- a Settings repository.

It serializes durable comparison intent only.

## Persistence boundaries

Three persistence/state classes remain distinct:

```text
ApplicationSettings / SettingsRepository
    typed application preferences, schema v5

workspace QSettings
    application UI workspace state such as geometry/layout-related preferences

Comparison Set artifact
    external user-owned ordered logical comparison data

P4-A ReviewSelectionState
    temporary runtime-only workflow state
```

P4-B does not bump ApplicationSettings schema and does not move Comparison Set payload
into QSettings.

## Deferred full-session persistence

Full application-session persistence would require a separate product contract for
which UI/analysis state is durable. It is intentionally deferred and must not be
introduced by expanding Comparison Set v1 with caches, workers, runtime ownership, or
unproven UI state.
