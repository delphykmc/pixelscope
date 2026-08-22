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
- If P4-A temporary Pick/Keep state is active, Inspect is rejected. P5-D never commits,
  clears, or reinterprets Picks on the user's behalf.
- Native Inspect supports one through six published Scene variants. More than six are
  never truncated; result-only exploration remains available.

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
- `storage_root_id` is not measurement identity and is intentionally excluded from
  `measurement_context_id`;
- `source_id`, SHA-256, dimensions, geometry, grids, and numerical measurements retain
  their existing schema-v2 authority.

## 4. Source resolution and identity verification

P5-D reuses P5-C logical storage authority.

For every source required by the chosen Scene:

1. look up the configured machine-local path for published `storage_root_id`;
2. validate the published portable POSIX `relative_path`;
3. resolve through the configured root with existing containment/symlink rules;
4. require the resolved logical root/path to equal the published locator exactly;
5. require an ordinary supported native image type (`PNG/JPG/JPEG/BMP`);
6. probe native dimensions from bounded headers;
7. compare dimensions with the published source metadata;
8. compare the resolver's streamed SHA-256 with the published SHA-256.

Verification is **all-or-nothing**. No Registered/Selected mutation occurs until every
required source passes. Missing root, missing source, path escape, duplicate resolved
source, unsupported type, changed dimensions, or changed hash leaves the local
comparison untouched and reports an explicit unavailable reason.

The resolver already computes SHA-256 while resolving an existing source. P5-D reuses
that digest and does not perform a second full-file hash pass.

## 5. Registration and Selected authority

After successful verification only:

- P5-D calls the canonical input registration path;
- an already-Registered physical source is reused by path identity;
- new source registrations are ordinary PixelScope registrations;
- the verified Scene source order becomes the requested Selected order;
- normal MainWindow Current Comparison Page, load, residency, preload, Difference, and
  analysis lifecycle runs unchanged;
- a registration failure before the Selected commit removes P5-D registrations made by
  that failed attempt and preserves the pre-Inspect local workspace.

P5-D does not maintain parallel source objects after the canonical registration step.
Its feature-local map only associates canonical document IDs with IQA `variant_id` for
spatial presentation.

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

## 7. Stale local intent and Return invalidation

A Return snapshot must never overwrite newer user intent.

After Inspect begins, these non-IQA mutations invalidate Return:

- a newer Selected mutation;
- removal/change of Registered sources relevant to the snapshot;
- a newer layout choice;
- a newer Primary choice.

Active alone is not an invalidation trigger because Active changes are common during
ordinary inspection. If the captured Active remains applicable, Return restores it.

When Return is invalidated, IQA spatial presentation is cleared and the current local
workspace remains authoritative.

## 8. IQA Reference versus local Primary

These are independent concepts:

- **Reference** selects the IQA comparison operand used by Results/spatial relative
  values;
- **Primary** selects local viewer presentation/reference priority.

Changing Primary does not rewrite IQA Reference. Changing IQA Reference does not
choose a Primary image.

For spatial Relative mode the per-cell value is always raw target/reference orientation
from schema-v2 semantics, not quality-oriented sign-flipped presentation.

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
Current Comparison Page/viewer protection remains authoritative.

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

A callback may publish only if all relevant identity still matches:

- controller generation;
- currently opened result identity;
- selected IQA Scene;
- current spatial request identity (Scene, attribute, Reference, aggregation-mode
  presentation context).

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
- invalid source/pair cells.

## 15. Automated validation matrix

Focused tests must cover at least:

- old schema-v2 omission compatibility;
- locator parse/validation and fingerprint independence;
- all-or-nothing verification;
- missing/moved/hash/dimension failure;
- >6-variant non-truncation;
- Absolute `S1/W` and invalid-cell handling;
- raw relative power and signed math;
- hand-calculated draw/hit-test geometry;
- Block Inspector sufficient statistics;
- passive Results isolation;
- P4-A Pick guard;
- already-Registered source reuse;
- exact Scene Selected order;
- Return first-snapshot semantics;
- Single View page/Active restoration;
- newer-local-intent invalidation;
- Reference/Primary independence;
- stale Scene/result callbacks and shutdown safety.

Repository gate on the exact review head:

```powershell
.\.venv\Scripts\python.exe -m pytest `
    tests\unit\test_p5d_scene_inspection.py `
    tests\ui\test_p5d_viewer_linked_inspection.py `
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
3. inspect a valid 2–6-variant Scene and confirm source order/reuse;
4. navigate to another IQA Scene and confirm the original Return target remains;
5. Return from both Single and Multi View, including a Selected set larger than six;
6. change local Selected/layout/Primary during Inspect and confirm stale Return cannot
   overwrite the newer choice;
7. switch IQA Reference and Primary independently;
8. compare spatial overlay/block inspector with known non-zero-origin/non-integer-affine
   fixture geometry;
9. inspect invalid/pair-invalid cells;
10. exercise Display Gain, Difference, ROI, Line Profile, zoom/pan/sync while inspected;
11. rapidly change Scene/attribute/Reference and open another Result;
12. close/recreate the window while source/grid work is active.

## 17. Explicit exclusions

P5-D does not implement:

- Recent IQA Results/history (P5-E);
- Session schema v2 or persisted IQA Return state;
- arbitrary >6-source local viewer presentation;
- GPU/server implementation;
- authentication/SSO/credentials (P6);
- source residency/preload redesign;
- full-resolution IQA heatmap buffers;
- packaging/signing/updater work (P7).
