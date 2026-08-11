# PixelScope decisions

This document records current durable architecture/product decisions. Historical
implementation details belong in completed execution plans and PR history.

## Runtime ownership

- `Registered → Selected → Current Comparison Page → Presented → Resident when
  required` is the authoritative hierarchy.
- `Analysis Working Set = Current Comparison Page`.
- Selected may exceed six; Current Comparison Page is derived and bounded to six.
- Selected alone is not source-residency protection authority.
- Comparison Page navigation creates no speculative preload.
- P2 preload remains Folder Position `+1`, one position ahead, max-one speculative
  worker with existing promotion semantics.
- Difference cache and native-source residency remain separate budgets/owners.

## Numerical/presentation decisions

- Native decoded source remains analysis authority.
- Difference keeps P3 same-bit native-domain and mixed-bit normalized-domain rules.
- RAW Black/White metadata remains independent from Difference numerical domain.
- Display Gain is presentation-only and remains application-session state, not a
  persisted setting or Comparison Set field.
- Split Channel and Difference documents are derived/transient identities.

## P4-A closure

P4-A Review Selection & Curation merged as PR #29 at
`3486146494076e9b513843b90ec44e504043729e`.

Accepted P4-A decisions:

- direct Pick in Multi View; no explicit Review Select mode;
- first Pick captures ordered Selected baseline;
- temporary Pick Set can span Comparison Pages;
- Keep Selection filters baseline ordering and is the only curation command that
  changes logical Selected;
- Pick state is runtime ID-only and owns no decode/residency/preload/cache/analysis;
- Pick Set and captured baseline are never persisted by P4-B.

## P4-B accepted decisions — Comparison Set Persistence

### Comparison Set, not full Session

P4-B persists a reusable **Comparison Set**, not a full PixelScope application
session. Full-session persistence is deferred until a concrete workflow requires it.

### External versioned artifact

The user artifact uses dedicated `.pixelscope` JSON with:

```text
kind = pixelscope-comparison-set
schema_version = 1
```

It is separate from ApplicationSettings and workspace QSettings.

### Primary durable payload

The authoritative persisted payload is ordered logical Selected source references.
Optional stable context is Active source, Primary source, layout mode, and an already
resolved deterministic RawProfile for an applicable RAW member.

Current Comparison Page remains derived and is never serialized independently.
`_page_start` is runtime derivation state, not artifact state.

### Persistent identity

Runtime document IDs are not persistent identity. v1 uses normalized absolute local
source paths. Duplicate path identities are rejected.

v1 intentionally has no fuzzy relocation, filename-only matching, size-only
matching, recursive moved-file search, or automatic path repair.

### Runtime state is not serialized

Comparison Set v1 excludes:

- decoded source/preview/gained-preview arrays;
- source residency/LRU/protection and Difference caches;
- workers, preload state, tokens, request/generation serials;
- P4-A Pick Set/baseline;
- Split/Difference derived documents;
- ROI/Line/Saved ROI/Plots state;
- Display Gain;
- window/dock/splitter geometry inside the artifact;
- Recent history/diagnostics.

### Save semantics

Save uses current logical Selected in exact order. A temporary Pick Set is not saved.
To save a curated subset the user first applies Keep Selection.

Saving does not force decode/residency, does not clear Pick state, and uses an atomic
same-directory temporary-write/replace strategy.

### Open semantics

Artifact syntax/schema is validated before runtime mutation. Existing Registered
catalog is retained. Saved loadable members are registered/reused, then logical
Selected is replaced in saved order through the inherited Selected mutation path.

Saved Active is restored when loadable; otherwise the first loadable member is the
Active fallback. Current Comparison Page is then derived from that Selected position.
Saved Primary is restored only when compatible with the current page/local Primary
contract. Stable layout mode is restored through existing layout authority.

Because open uses the inherited Selected mutation boundary, captured P4-A curation
state invalidates through existing logic rather than a P4-B-specific lifecycle.

### Missing/corrupt/future behavior

- Partial missing sources: load valid members in saved order and report missing
  members compactly.
- Zero loadable sources: current workspace remains unchanged.
- malformed JSON/wrong kind/invalid required fields/future schema: reject before
  workspace mutation.
- Future schema is not guessed, migrated destructively, or rewritten.
- Same-version unknown fields are ignored; required/known fields remain validated.

### RAW policy

Resolved RAW profile data may be stored only when already available. Existing
RawProfile validation is reused. Save does not prompt unresolved RAW. On open, saved
resolved profile data is associated before foreground use; unresolved members follow
the inherited lazy foreground profile-resolution contract.

### Settings decision

P4-B does not change Settings schema v5. Comparison Set artifact, ApplicationSettings,
workspace QSettings, and P4-A temporary state remain separate ownership domains.

## P4-C accepted planning boundary

P4-C is **Recent Entries & Comparison Set Entry UX**. It begins only after P4-B merge.
Recent history will distinguish `image`, `folder`, and `comparison_set`, and will
reuse each existing user-entry workflow rather than reimplement it. Operational
history is separate from ApplicationSettings and from runtime source ownership.
