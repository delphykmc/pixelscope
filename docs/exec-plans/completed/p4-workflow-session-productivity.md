# Execution plan: P4 — Workflow & Session Productivity

Status: Complete
Owner: repository owner + P4 orchestration agents
Completed baseline: PR #35 / main
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`

## Goal

P4 improved large-selection review, durable workspace reuse, analysis export, and
cross-feature lifetime behavior without creating a second source, selection,
analysis, cache, worker, preload, or residency authority.

The inherited runtime hierarchy remained authoritative throughout P4:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
Presented
    ↓
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

## Completed sequence

`P4-0 → P4-A → P4-B → P4-C → P4-E → P4-F → P4 Complete`

| Slice | Result |
|---|---|
| P4-0 | P3 closure and P4 program setup — PR #28 |
| P4-A | Review Selection & Curation — PR #29 |
| P4-B | Comparison Set Persistence — PR #30 |
| P4-C | Session Persistence & Typed Recent — PR #31 |
| PR #32 | Display Gain / Difference runtime stabilization |
| PR #33 | Difference/source-curation lifecycle alignment |
| P4-E | Analysis Export Productivity — PR #34 |
| P4-F | Integration & Workflow Hardening — PR #35 |

P4-D Saved/named/multiple ROI was deliberately deferred. Alpha
Overlay/Flicker/Wipe and arbitrary-angle Line Profile were also deferred and were
not P4 completion blockers.

## P4-A — Review Selection & Curation

P4-A added temporary source-only curation for large Selected sets.

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page
    ↓
direct temporary Pick Set
    ↓ Keep Selection
new Selected subset
```

Key contracts:

- native source tiles expose Pick directly; there is no Review Select mode;
- the first Pick captures the baseline ordered Selected IDs;
- picks persist across Comparison Pages but own no source residency, decode,
  preload, Difference, or analysis work;
- Clear Selection clears only temporary Picks;
- Keep Selection is the only curation action that mutates logical Selected and
  preserves the captured baseline order;
- Split/Difference derived documents are not independent Pick identities;
- temporary Picks are not persisted.

P4-A merged as PR #29 at
`3486146494076e9b513843b90ec44e504043729e`.

## P4-B — Comparison Set Persistence

P4-B introduced the first external `.pixelscope` Comparison Set v1 artifact using
normalized absolute local source paths. It persisted ordered Selected source
references, applicable Active/Primary/layout state, and minimum resolved RAW
metadata while excluding runtime arrays, caches, workers, residency/preload state,
Difference state, Display Gain, ROI/Line, and Picks.

P4-B merged as PR #30 at
`3a19589e6cbad5fa8c814c522df6a553f59ee340`.

## P4-C — Session Persistence & Typed Recent

P4-C generalized new `.pixelscope` writes to PixelScope Session v1 while retaining
legacy Comparison Set v1 read compatibility.

Session v1 persists durable workspace intent:

- Registered membership and minimum RAW reconstruction metadata;
- exact ordered Selected paths;
- a Current Comparison Page source-path anchor;
- applicable source Active and Primary;
- stable layout;
- ROI, Line, Display Gain, and applicable Split Channels state;
- a regenerable Difference recipe only when its A/B both belong to the saved page.

Session restore remains a bounded staged reconstruction using the inherited source,
residency, Display Gain, and explicit Difference Calculate paths. Runtime arrays,
cache contents, worker/token state, and Picks remain non-persistent.

Typed Recent keeps independent bounded history for Images, Folders, and Sessions and
is observer metadata rather than workspace authority.

P4-C merged as PR #31 at
`436033a0d99513fe8db35f08305395127e430af2`.

## PR #32 / PR #33 runtime stabilization

PR #32 moved heavy Display Gain/Difference presentation work onto bounded application
workers, preserved source-to-viewer identity through presentation churn, rejected
stale results, and hardened application shutdown.

PR #33 made active Difference provenance explicit across source curation. Keep
Selection always tears down the active Difference before Selected mutates; passive
navigation never promotes a cached map to active Difference state; explicit
Calculate remains the sole establishment path.

PR #32 merged at
`e1ccf264f86e37b438c923faceae96c3ecb539b7`.
PR #33 merged at
`51a540c92c372d71e02fd849fb5e0d406d0e9327`.

## P4-E — Analysis Export Productivity

P4-E added focused consumers of already-established results:

- current settled Difference presentation PNG export;
- exact plotted Histogram CSV;
- exact plotted Line Profile CSV;
- Difference metrics CSV / clipboard productivity;
- shared timestamped Statistics export orchestration.

Export never becomes numerical, Difference, source, residency, preload, or
generation authority.

P4-E merged as PR #34 at
`79ee74134f1ebef9dd13f82e49f8e34407bb78f4`.

## P4-F — Integration & Workflow Hardening

P4-F closed cross-feature gaps without adding a broad new feature. It hardened:

- Session Save page-anchor authority independently of Active/Primary fallback;
- closed-window Display Gain subscription and preview-worker lifetime;
- repeated production Display Gain composition so controls and shortcuts remain
  idempotent;
- cross-feature curation → Difference teardown → Session Save behavior;
- Session restore → explicit Difference reconstruction → settled export behavior.

P4-F merged as PR #35. The resulting main merge commit is
`d1d1fbe8fc7ee81855e5e037bcecc1278435e298`.

## Deferred after P4

The following remain future candidates rather than incomplete P4 work:

- saved/named/multiple ROI management;
- Alpha Overlay / Flicker / Wipe;
- arbitrary-angle Line Profile with an explicit discrete sampling contract.

## Validation policy at closure

P4 runtime/UI slices were validated by the repository owner on Windows using focused
regressions followed by the repository-standard pytest/Ruff/mypy/docs checks as
appropriate. Historical PASS evidence is not reused for later phase heads.

P5 begins from the merged PR #35 baseline and must preserve the P2/P3/P4 ownership,
resource, persistence, and stale-result contracts rather than extending them by
accident.