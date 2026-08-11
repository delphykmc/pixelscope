# UI implementation status

Snapshot: 2026-08-11
Merged runtime baseline: P4-A / PR #29 at
`3486146494076e9b513843b90ec44e504043729e`

## Implemented baseline

- Files workspace with Registered/Selected distinction.
- Auto / Single View / Multi View layouts.
- Current Comparison Page controls for large Selected sets.
- native Statistics, Histogram, Line Profile, Difference, Split Channels.
- Display Gain presentation control.
- workspace/Plots UI behavior from P1.
- Settings UI/runtime integration from P2.
- P4-A direct temporary Pick curation.

## P4-A — Complete

P4-A Review Selection & Curation merged as PR #29.

Production presentation row includes the temporary curation controls:

```text
Layout | Page | Display Gain | Selected N | Clear Selection | Keep Selection
```

Eligible Multi View native source tiles expose **Pick** directly. Pick state is
visually distinct from Active and Primary. There is no explicit Review Select mode
and no user-facing Cancel control.

Temporary Picks are application-session state only and are not persisted.

## P4-B — Comparison Set Persistence — active branch

Branch: `feature/p4-b-comparison-set-persistence`

P4-B adds File-menu commands:

```text
Open Comparison Set...
Save Comparison Set...
```

The Save command tooltip explicitly states that current logical Selected is saved and
that temporary Picks are not saved; users should apply Keep Selection first when they
want to persist the curated subset.

The commands are orchestrated by `ComparisonSetController`; JSON schema/storage is not
implemented inside `MainWindow`.

Current implementation behavior:

- `.pixelscope` v1 artifact;
- ordered logical Selected source paths;
- optional Active/Primary source paths;
- stable layout mode;
- resolved RawProfile payload when already available;
- existing Registered non-set sources preserved on open;
- missing source subset skipped/reported;
- zero-loadable/invalid artifact leaves workspace unchanged;
- Current Comparison Page is derived after Selected/Active restore rather than stored;
- saved RAW profile avoids an unnecessary new resolution prompt; unresolved RAW stays
  on the existing lazy foreground workflow;
- open uses the inherited Selected mutation path and therefore invalidates temporary
  P4-A curation through existing integration;
- large saved sets do not gain Selected-wide source residency/preload authority.

P4-B does not add Recent UI, full-session UI, Saved ROI, Display Gain persistence, or
new workspace geometry persistence.

P4-B remains **not Complete** until owner-local validation, independent review, and
merge.

## Planned P4-C

After P4-B merge, P4-C will add one coherent **Open Recent** surface distinguishing
Images, Folders, and Comparison Sets plus Clear Recent. No P4-C runtime code belongs
on the P4-B branch.
