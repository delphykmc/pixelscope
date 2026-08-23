# P5-D — Viewer-linked Scene Inspection Contract

Status: Active implementation/review

Base authority: `main@24b328d02c0cd56fb79920e069af06d6e4cb706f`

This document freezes the P5-D feature-local contract. It does not replace
`REMOTE_IQA_CONTRACT.md` or `REMOTE_IQA_V2_SPEC.md`; it specializes those authorities
for explicit native Scene inspection.

## 1. Product boundary

Remote IQA Results browsing remains passive.

```text
Open Result
    ↓
Overview / Scene Trend / source metadata
    ↓                     no local workspace mutation
explicit Inspect in Viewer
    ↓
verify every required Scene source
    ↓
canonical Registered / Selected / Current Comparison Page
    ↓
existing PixelScope viewer + optional spatial overlay
    ↓
explicit Return
```

P5-D must not create a second Files registry, Selected set, Current Comparison Page,
source cache, residency manager, preload owner, Difference owner, native-analysis
owner, viewer stack, or Session authority.

The inherited local hierarchy remains:

```text
Registered
    ↓
Selected
    ↓
Current Comparison Page        # max 6
    ↓
Presented
    ↓
Resident when required
```

`Analysis Working Set = Current Comparison Page`.

## 2. Explicit Inspect and P4-A interaction

- Merely selecting an IQA Scene never changes Files, Selected, Current Comparison Page,
  Primary, Difference, residency, preload, ROI, Line, or Session state.
- **Inspect in Viewer** is the explicit mutation boundary.
- If P4-A temporary Pick/Keep state is already active, initial Inspect is rejected.
  P5-D never commits, clears, or reinterprets Picks on the user's behalf.
- If the user starts a new temporary Pick after Inspect, that is newer local intent:
  P5-D invalidates Return and preserves the Pick state. Return must never silently clear
  a newer curation baseline.
- Native Inspect accepts one through six published **variant bindings**. More than six
  are never truncated; result-only exploration remains available.
- Multiple variant bindings may intentionally reference the same concrete `source_id`.
  Those bindings retain separate IQA identities but share one canonical native Files
  document/source identity.

## 3. Portable source locator

Schema-v2 Scene source bindings may contain:

```json
{
  "variant_id": "candidate",
  "source_id": "source-...",
  "storage_root_id": "shared-iqa",
  "relative_path": "dataset/scene/source.png",
  "sha256": "...",
  "width": 1920,
  "height": 1080
}
```

`storage_root_id` is optional additive **location metadata**.

Rules:

- schema version remains 2;
- older schema-v2 artifacts with no `storage_root_id` remain readable by the canonical
  result reader;
- omission disables native Inspect for that source because PixelScope must not guess a
  machine-local root;
- `storage_root_id` uses the same identifier validation as P5-C settings;
- `storage_root_id` is not immutable source identity and is excluded from `Source`
  equality;
- `storage_root_id` is not measurement identity and is intentionally excluded from
  `measurement_context_id`;
- `source_id`, SHA-256, dimensions, geometry, grids, and numerical measurements retain
  their existing schema-v2 authority.

The normative additive field contract is also recorded in `REMOTE_IQA_V2_SPEC.md`.

## 4. Source resolution, decode binding, and identity verification

P5-D reuses P5-C logical-storage and ordinary-image acceptance authority.

For every source required by the chosen Scene:

1. look up the configured machine-local path for published `storage_root_id`;
2. validate the published portable POSIX `relative_path`;
3. resolve through the configured root with existing containment/symlink rules;
4. require the resolved logical root/path to equal the published locator exactly;
5. require an ordinary supported native image type (`PNG/JPG/JPEG/BMP`);
6. run the same bounded P5-C ordinary-image dimension probe, including supported BMP
   headers and the same JPEG metadata scan budget;
7. compare dimensions with the published source metadata;
8. read/decode the ordinary source from one encoded byte buffer;
9. compute SHA-256 over that exact encoded buffer and require it to equal the published
   SHA-256;
10. carry the resulting decoded `ImageDocument` forward as the verified generation.

Verification is **all-or-nothing**. No Registered/Selected mutation occurs until every
required binding has resolved and every unique native source has passed locator,
header, decode, dimension, and exact encoded-SHA checks. Missing root, missing source,
path escape, unsupported type, changed dimensions, changed hash, or distinct source
identities claiming one physical locator leaves the local comparison untouched and
reports an explicit unavailable reason.

The exact-decoded-generation rule is intentional. A separate pre-decode hash is not
sufficient because an already-Registered resident document may contain pixels decoded
from older bytes at the same path, and a file may change between verification and a
later independent decode. P5-D therefore commits the already-decoded object whose
encoded byte buffer produced the verified SHA.

A repeated locator is allowed only when it represents the same immutable `source_id`.
Such repeated variant bindings reuse one decode and one canonical Files document.

## 5. Registration, decoded generation, and Selected authority

After successful all-source verification only:

- P5-D calls the canonical input registration path;
- an already-Registered physical source is reused by path identity;
- new source registrations are ordinary PixelScope registrations;
- repeated variant bindings for one `source_id` collapse to one canonical native
  document while P5-D retains all corresponding `variant_id` aliases;
- the verified unique native-source order becomes the requested Selected order;
- Selected/current-page authority is established before the verified decoded arrays are
  committed, so normal residency enforcement treats them as correctness-protected and
  cannot evict/reload them from disk between verification and presentation;
- any ordinary load started by canonical selection receives a newer load token and is
  stale-dropped when the exact verified decoded generation is committed;
- if an already-resident document's encoded SHA differs, the exact verified decoded
  generation replaces it under the same document ID, its source generation advances,
  dependent source-view caches are invalidated, and generation-keyed downstream caches
  cannot mistake old pixels for the new source;
- normal MainWindow Current Comparison Page, residency, preload, Difference, and native
  analysis ownership otherwise remains unchanged.

P5-D does not maintain parallel source arrays after commit. Feature-local state keeps
only result/Scene identity and the document-to-variant binding aliases needed for IQA
presentation.

## 6. Return snapshot

The first successful Inspect captures one transient snapshot:

- exact Selected document-ID order;
- current Comparison Page anchor;
- applicable Active document;
- applicable Primary document;
- layout mode.

The snapshot is intentionally not Session persistence. It exists only for the live
window/inspection sequence.

Linked IQA Scene navigation reuses the same first snapshot. Inspecting Scene 2 after
Scene 1 must not replace the original local Return target.

Return restores only still-applicable local comparison intent. It explicitly commits
the captured Comparison Page after Selected is restored, because canonical selection
mutation initially resets page state. Single View restores the captured Active source
as the actual displayed viewer document. Multi View restores the captured Primary and
then activates the captured Active tile where still present.

ROI/Line/Difference-derived transient presentation is not serialized into this P5-D
snapshot. Those features continue to obey their existing canonical selection/change
lifecycle.

## 7. Stale local/settings intent and Return invalidation

A Return snapshot or pending source-verification callback must never overwrite newer
user/configuration intent.

After Inspect begins, these non-IQA mutations invalidate Return:

- a newer Selected mutation;
- removal/change of Registered sources relevant to the snapshot;
- a newer layout choice;
- a newer Primary choice;
- a newly activated temporary P4-A Pick baseline.

Active alone is not an invalidation trigger because Active changes are common during
ordinary inspection. If the captured Active remains applicable, Return restores it.

Remote IQA logical-root mappings are live machine-local configuration. A mapping
change increments the P5-D locator revision, cancels/invalidate any pending native
source verification started under the old mapping, and refreshes Inspect availability
against the newest settings. An old verification callback cannot commit after a root
remap.

When Return is invalidated, IQA spatial presentation is cleared and the current local
workspace—including any new Pick state—remains authoritative.

## 8. IQA Reference versus local Primary

These are independent concepts:

- **Reference** selects the IQA comparison operand used by Results/spatial relative
  values;
- **Primary** selects local viewer presentation/reference priority.

Changing Primary does not rewrite IQA Reference. Changing IQA Reference does not
choose a Primary image.

For spatial Relative mode the per-cell value is always raw target/reference orientation
from schema-v2 semantics, not quality-oriented sign-flipped presentation.

When several variant slots intentionally share one concrete `source_id`, one native
viewer tile represents that concrete image while the result domain retains all variant
aliases. Native source identity is not duplicated merely to manufacture one tile per
variant binding.

## 9. Spatial numerical contract

P5-D consumes the existing lazy schema-v2 Scene grid artifact. It does not introduce a
second parser.

For one source/attribute cell:

```text
W  = weight_sum
S1 = weighted_sum
S2 = weighted_square_sum
N  = valid_count
```

Absolute cell value:

```text
mean = S1 / W
```

A cell is display-valid only when its published validity and sufficient-statistic
invariants are valid.

Relative power cell for target `T` and reference `R`:

```text
10 * log10((mean_T + epsilon) / (mean_R + epsilon))
```

using the same canonical schema-v2 power-ratio helper as non-spatial comparison.
Only pair-valid cells contribute. Undefined/nonfinite cells stay invalid.

Relative signed cell:

```text
mean_T - mean_R
```

No quality-direction sign flip is applied to the spatial raw relative field.

Shared overlay scale is computed across displayed valid Scene variants for the selected
attribute. Relative and signed fields are centered around zero. Invalid cells are not
painted as valid zero.

The selected scalar Scene aggregation mode remains a **reduction** of the underlying
field; switching Mode 1/Mode 2 must not silently redefine the raw per-cell values.

## 10. Geometry contract

All geometry uses continuous source pixel-edge coordinates already established by
schema v2.

The drawing path is:

```text
analysis cell polygon
    ↓ inverse(source_to_analysis)
source polygon
    ↓ clip to source bounds
existing ImageViewer ViewBox
```

The hit-test path is:

```text
source cursor point
    ↓ source_to_analysis
analysis point
    ↓ valid_rect + grid origin/block geometry
(row, column)
```

Drawing and hit-testing therefore share:

- the same `source_to_analysis` affine;
- non-integer transforms;
- non-zero grid origins;
- `valid_rect`;
- block width/height;
- discarded right/bottom borders.

A geometric hit may identify a published invalid cell so Block Inspector can say
`invalid`; painting still filters invalid/pair-invalid cells.

## 11. Overlay ownership and memory policy

Spatial visualization uses vector `QGraphicsItem` polygons attached to the existing
`ImageViewer.view_box`.

It must not allocate a source-resolution heatmap/alpha bitmap. Feature memory scales
with grid-cell count and the canonical lazy grid artifact, not with image pixel count.

P5-D does not add source-residency protection solely for overlay ownership. Existing
Current Comparison Page/viewer protection remains authoritative. The verified decoded
generation is committed only after those canonical page protections are active.

## 12. Block Inspector

Hover/click may expose bounded per-cell data:

- Scene ID;
- attribute ID;
- variant/source ID;
- row/column;
- source validity;
- W/S1/S2/valid_count;
- per-cell source mean;
- Reference source and reference mean when relative;
- pair validity;
- raw relative value;
- analysis bounds;
- mapped source polygon.

This is diagnostic/presentation information derived from published schema-v2 data. It
never writes measurements back to the result.

## 13. Async/stale-result rules

Scene verification and spatial-grid preparation run through bounded feature-local task
workers.

A source-verification callback may publish only if all relevant identity still matches:

- controller generation;
- currently opened result identity;
- selected IQA Scene;
- local-intent generation captured at verification start;
- Remote IQA logical-root settings revision captured at verification start.

A spatial callback additionally requires the current spatial request identity (Scene,
attribute, Reference, aggregation-mode presentation context).

Opening another IQA Result cancels active Inspect/spatial work and prevents the old
result from becoming newly inspectable while the new result is loading. Shutdown
cancels feature-local workers and clears overlays. Stale callbacks are ignored.

## 14. Deterministic fixture requirements

P5-D fixtures extend the canonical schema-v2 golden writer with real native sources and
portable locators. Required scenarios include:

- valid sources;
- missing source;
- hash mismatch;
- dimension mismatch;
- missing grid;
- corrupt grid;
- non-integer affine transform;
- non-zero grid origin;
- discarded border;
- multiple attributes;
- invalid source/pair cells;
- an already-Registered resident source whose disk bytes changed;
- repeated variant bindings to one concrete `source_id`;
- P5-C/P5-D BMP/JPEG header-probe parity;
- root-mapping changes while verification is pending.

## 15. Automated validation matrix

Focused tests must cover at least:

- old schema-v2 omission compatibility;
- locator parse/validation and fingerprint independence;
- P5-C/P5-D ordinary-image probe parity;
- exact encoded-buffer SHA binding to the decoded generation;
- all-or-nothing verification;
- missing/moved/hash/dimension failure;
- already-Registered stale-resident replacement;
- repeated `source_id` multi-variant collapse without losing variant aliases;
- distinct source identities aliasing one locator rejection;
- >6-variant non-truncation;
- Absolute `S1/W` and invalid-cell handling;
- raw relative power and signed math;
- hand-calculated draw/hit-test geometry;
- Block Inspector sufficient statistics;
- passive Results isolation;
- pre-Inspect P4-A Pick guard;
- post-Inspect Pick preserving curation while invalidating Return;
- already-Registered source reuse;
- exact unique-source Selected order;
- Return first-snapshot semantics;
- Single View page/Active restoration;
- newer-local-intent invalidation;
- root-mapping revision stale-drop and live availability refresh;
- Reference/Primary independence;
- stale Scene/result callbacks and shutdown safety.

Repository gate on the exact review head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5d_scene_inspection.py `
    tests\unit\test_p5d_source_locator_identity.py `
    tests\unit\test_p5d_review_closeout.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
    tests\ui\test_p5d_stale_inspection.py `
    tests\ui\test_p5d_review_closeout.py `
    -q

.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Do not record PASS until output from the exact head is observed.

## 16. Owner Windows manual validation

Before merge, verify with a production-composed MainWindow and realistic shared/local
sources:

1. open a COMPLETE and PARTIAL schema-v2 Result without changing local Selected;
2. verify Inspect disabled/rejected for missing locator/root, changed source, and
   >6-variant Scene;
3. inspect a valid 2–6-binding Scene and confirm unique-source order/reuse;
4. inspect a Scene where two variants intentionally share one `source_id` and confirm
   one Files/native source is used while result variant identities remain available;
5. replace bytes at an already-Registered resident source path and confirm Inspect shows
   the published/verified pixels rather than the old resident decode;
6. navigate to another IQA Scene and confirm the original Return target remains;
7. Return from both Single and Multi View, including a Selected set larger than six;
8. change local Selected/layout/Primary during Inspect and confirm stale Return cannot
   overwrite the newer choice;
9. start a new Pick after Inspect and confirm the Pick remains while Return is
   invalidated/disabled;
10. change a Remote IQA root mapping during pending Inspect verification and confirm the
    old callback cannot publish and Inspect availability reflects the new mapping;
11. switch IQA Reference and Primary independently;
12. compare spatial overlay/block inspector with known non-zero-origin/non-integer-affine
    fixture geometry;
13. inspect invalid/pair-invalid cells;
14. exercise Display Gain, Difference, ROI, Line Profile, zoom/pan/sync while inspected;
15. rapidly change Scene/attribute/Reference and open another Result;
16. close/recreate the window while source/grid work is active.

## 17. Explicit exclusions

P5-D does not implement:

- Recent IQA Results/history (P5-E);
- Session schema v2 or persisted IQA Return state;
- arbitrary >6-variant-binding local viewer presentation;
- GPU/server implementation;
- authentication/SSO/credentials (P6);
- source residency/preload redesign;
- full-resolution IQA heatmap buffers;
- packaging/signing/updater work (P7).
