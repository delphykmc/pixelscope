# PixelScope product specification

## Product purpose

PixelScope is a local engineering image comparison and analysis application. It
supports ordinary images and profile-described RAW while preserving native source
values for numerical analysis.

## Core workspace model

```text
Registered
    ↓ user selection
Selected
    ↓ ordered page derivation
Current Comparison Page        # up to 6
    ↓ presentation
Presented
    ↓ native-source lifecycle
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

Registered count, Selected count, page size, presentation capacity, and decoded
source residency are independent concepts.

## Input intent

- **Open Images...** and direct image-file drag/drop register explicitly chosen
  images and make them logical Selected in input order.
- **Open Folder...** and folder drag/drop register supported contents without
  replacing current Selected/presentation.
- Supported image suffixes remain PNG/BMP/JPEG/RAW according to the current reader
  contract.
- RAW follows deterministic profile/sidecar validation and lazy foreground resolution
  established in P3-D.

## Large selection and analysis

Selected may exceed six. Current Comparison Page is derived in fixed six-image
chunks. Page navigation does not change Selected membership and does not create
speculative preload.

Statistics, Histogram, Line Profile, page-derived Difference context, foreground
loading, and generic protection use Current Comparison Page rather than all Selected.

## P4-A Review Selection & Curation

P4-A is a temporary workflow for reducing a large logical Selected set.

Eligible native-source tiles in Multi View expose **Pick**. The first Pick captures
the current ordered Selected baseline. Picks may span pages. The command row shows
temporary count plus **Clear Selection** and **Keep Selection**.

- Clear Selection clears temporary picks only.
- Keep Selection replaces logical Selected with picked members in captured baseline
  order.
- Non-picked sources remain Registered.
- Pick state is not residency/preload/cache/analysis authority.
- Pick Set and captured baseline are temporary and non-persistent.

## P4-B Comparison Set Persistence

### User commands

File menu provides:

```text
Open Comparison Set...
Save Comparison Set...
```

User-facing terminology is **Comparison Set**. P4-B does not present this artifact as
a Session, Workspace Session, or Project Session.

### What Save Comparison Set stores

Save records current **logical Selected**, not the temporary P4-A Pick Set.

Comparison Set v1 stores:

- versioned artifact identity;
- ordered Selected local source paths;
- optional Active source path;
- optional Primary source path;
- layout mode (`Auto`, `Single View`, `Multi View`);
- already-resolved RawProfile data for applicable RAW sources.

If a user has only made temporary Picks, those Picks are not the save target. To save
the curated subset the user must first choose **Keep Selection**, then Save Comparison
Set.

Save does not force off-page decoding/residency and does not clear temporary Picks.
With no logical Selected, Save is a normal no-op with compact status feedback.

### Artifact format

Default extension: `.pixelscope`.

The JSON artifact carries:

```text
kind = pixelscope-comparison-set
schema_version = 1
```

Persistent source identity is a normalized absolute local path. Runtime document IDs
are not stored.

### Open Comparison Set behavior

Opening is a logical comparison-set restore, not a full workspace restore.

1. Parse and validate the artifact before changing runtime state.
2. Determine loadable saved source references.
3. Reuse already Registered saved sources or register missing ones through the normal
   input boundary.
4. Replace logical Selected with loadable members in saved order.
5. Restore saved Active when available, otherwise use first loadable Selected.
6. Derive Current Comparison Page from the Active Selected position.
7. Restore saved Primary only when compatible with existing page-local semantics.
8. Restore the stable layout mode.

Existing Registered sources that are not members of the opened Comparison Set stay
Registered.

Opening a Comparison Set changes logical Selected, so any captured temporary P4-A
curation state is invalidated by the same existing Selected-mutation boundary used by
other workflows.

### Missing and invalid artifacts

A valid artifact may contain missing/moved sources. PixelScope loads the available
members in saved order and reports unavailable paths compactly.

If no saved member is loadable, current workspace/Selected is unchanged.

Malformed JSON, wrong kind, unsupported/future schema version, missing required
fields, or invalid field types are rejected without mutating current workspace state.

No fuzzy moved-file search or automatic path repair is performed in v1.

### RAW behavior

Saving does not force unresolved RAW profile dialogs. If deterministic RawProfile data
is already resolved, it may be included. Otherwise only the source path is stored.

On open, a saved resolved RawProfile is validated/reused. An unresolved RAW remains
pending and uses the inherited lazy foreground profile-resolution workflow when its
native source is required.

### Privacy

A `.pixelscope` Comparison Set can contain absolute local filesystem paths. Users
should consider those paths potentially sensitive when sharing the artifact.

### Explicit non-goals for v1

Comparison Set v1 does not persist:

- the complete Registered catalog;
- Current Comparison Page/page_start;
- decoded source/previews/caches/residency/preload/workers;
- temporary Picks;
- ROI/Line/Saved ROI/Plots state;
- Display Gain;
- window/dock geometry;
- Recent history;
- a full application session.

Full-session persistence is deferred until a concrete workflow requires it.

## Numerical and resource invariants

P4-B does not alter Difference numerical semantics, RAW Black/White interpretation,
Display Gain math, Statistics/Histogram/Line Profile authority, source `nbytes`
accounting, Difference cache independence, or Folder Position preload behavior.
Settings schema remains v5.

## Planned P4-C

Recent Entries & Comparison Set Entry UX will be a separate bounded MRU/history
problem. It will distinguish image, folder, and comparison_set entries and reuse the
existing entry commands. It is not implemented as part of P4-B.
