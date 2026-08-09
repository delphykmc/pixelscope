# Execution plan: P3 — Image Semantics & RAW Processing

Status: Active
Owner: repository owner + P3 orchestration agents
Last updated: 2026-08-09
Current merged P3 baseline: roadmap replanning / PR #23 merge commit
`4c7d1bbbb4476134f76a204578098d35a03feca2`

## Goal

Stabilize image-comparison and RAW-viewing semantics while keeping PixelScope an
engineering inspection tool. Native decoded samples remain authoritative; viewer
presentation may improve without silently redefining analysis domains or growing
into a partial RAW-conversion pipeline.

P3 deliberately precedes Workflow & Session Productivity. Session persistence and
workflow features should capture stable image-analysis semantics rather than
encode compatibility or display rules that are about to change.

## Program sequence

`P3-0 → P3-A → P3-B → P3-C → P3-D → P3-E`

| Order | Slice | Purpose | Status / prerequisite |
|---|---|---|---|
| 0 | P3-0 roadmap transition | Close/archive P2 and establish P3 | Complete — PR #21 |
| 1 | P3-A Difference domain extension | Gray + mixed-bit Difference semantics | Complete — PR #22 |
| 2 | P3-B RAW native/display semantics | Native RAW authority + generic gain core + RAW activation | Implementation complete; final review follow-up revalidation/merge pending |
| 3 | P3-C visualization/display gain | Ordinary Gray/RGB/RGBA gain + RAW observability | Next after P3-B merge |
| 4 | P3-D RAW profile management | Reusable profiles and profile suggestion workflow | After P3-C |
| 5 | P3-E integration hardening | Cross-analysis regressions, docs, Windows characterization | After P3-D |

Each implementation slice starts from the latest merged prerequisite on `main`.
The semantic ordering above is authoritative unless a new owner decision changes
it.

## Why P3 and P4 are reordered

The previous roadmap placed Workflow & Session Productivity before RAW work. The
order remains changed because image semantics should be stable before persistent
sessions save or restore them.

P3-A closed the immediate Difference gap. P3-B defines RAW native/display
ownership and establishes a reusable display-gain primitive without exposing a
new ordinary-image feature. P3-C can then extend the same presentation primitive
to Gray/RGB/RGBA while preserving analysis domains.

Therefore:

- **P3 remains Image Semantics & RAW Processing.**
- **P4 remains Workflow & Session Productivity.**
- P5–P7 retain their previous order.

## P3-0 — Program transition

Status: Complete — merged as PR #21 at
`5738cee2d012b72790ecc340bf9eb4ed0ccae6d7`.

This slice was documentation only and established the P3 program.

## P3-A — Difference Gray / Mixed Bit-Depth Support

Status: Complete — merged as PR #22 at
`769588bf869847da844cfc0b77c008023d8b048b`.

The production contract now supports:

- `GRAY ↔ GRAY`;
- `RGB/RGBA ↔ RGB/RGBA`;
- Bayer ↔ Bayer only when the CFA pattern matches;
- explicit rejection of cross-family, dimension, and CFA mismatches;
- native code-domain Difference for equal effective bit depths;
- independent effective-full-scale normalization to `[0,1]` for mixed bit depths;
- `%FS` threshold semantics in normalized Difference;
- bounded float32 normalized computation/metrics;
- explicit cached Difference-domain metadata;
- compact Scope/Domain UI and short validation states.

RAW Black/White metadata, display transforms, preview values, demosaic output, and
implicit RGB→Gray conversion do not participate in P3-A normalization. That
separation remains an invariant for later P3 slices.

## P3-B — RAW Native & Display Semantics

Status: Implementation complete on `feature/p3-b-raw-native-display-semantics`.
Owner/local Windows quality validation passed on
`424144215b1df97c71a84ddca79a17bfccb1feef`, including the generic gain core,
RAW Gain runtime behavior, and `+` / `-` stepping. Final independent re-review
found one merge blocker: window-wide gain shortcuts intercepted the Files tree's
native `+` / `-` expand/collapse keys. The follow-up scopes the command to the
viewer-presentation subtree and adds real key-routing coverage. Latest-head
owner/local revalidation and merge are pending.

### Native-source authority

- Decoded RAW samples remain authoritative and unchanged in
  `ImageDocument.source`.
- Existing `black_level` and `white_level` profile metadata remain supported with
  their current JSON/schema compatibility.
- Black/White metadata and display gain do not alter pixel inspection,
  Statistics, Histogram, Line Profile source data, Split Channels, source
  residency accounting, or P3-A Difference.
- P3-A Difference remains governed by effective bit depth/full scale and its own
  native/normalized domain contract.
- Display-only gain changes do not bump `ImageDocument.generation`, reload/decode
  source, or redefine cache identity.

### Generic display-gain architecture

P3-B establishes one generic presentation primitive:

```text
display = anchor + gain * (source - anchor)
```

The generic implementation belongs to `core.display_transform`, not to a RAW
profile model. RAW-specific code selects anchors and display range, then delegates
the numerical transform to that generic layer.

Required core properties:

- scalar anchor is supported, including `anchor=0` for later ordinary images;
- gain and display-range normalization may be represented as one float32 affine
  scale/offset and applied in place to a float32 scratch buffer;
- no full-frame float64 gain path;
- no unnecessary full-frame temporary/copy beyond the required derived preview
  scratch/result ownership;
- an array/channel view can be targeted, allowing future RGBA gain to process RGB
  while preserving alpha;
- gain `1×` remains identity at the gain primitive, and viewer runtime retains the
  stronger fast path of reusing the canonical 1× preview.

P3-B does **not** activate this generic core for ordinary Gray/RGB/RGBA viewer
content. The product surface in P3-B remains RAW-only.

### RAW anchor and display semantics

At 1× display gain, RAW maps the native code domain
`0..((1 << bit_depth) - 1)` to the uint8 preview range. Black is not implicitly
subtracted and White is not promoted to display full scale.

For gained RAW presentation:

- RAW Gray scalar `black_level` is the anchor;
- schema-valid RAW Gray four-value Black Level remains compatible and uses the
  pre-P3-B global-preview anchor `min(black_level)`;
- RAW Bayer uses R/Gr/Gb/B channel-specific Black Levels by CFA parity where a
  tuple is available;
- split Bayer channel views use the corresponding named-channel anchor;
- scalar Bayer Black Level applies the same anchor to all CFA channels;
- Bayer processing operates on parity-plane views and does not build a full-size
  Black Level map;
- `white_level` remains stored metadata and is not used for 1× or gained display.

Arithmetic is promoted to float32 before anchor subtraction semantics can cause
negative residuals. The implementation uses algebraically equivalent fused
scale/offset processing, and clipping is deferred to the final display conversion.

### UI/runtime boundary

- Product startup installs one compact toolbar `RAW Gain` control with
  1×/2×/4×/8×/16× choices.
- The gain state is application-session-only and is not stored in `RawProfile`,
  workspace QSettings, or application Settings; schema remains v5.
- Single and Multi View RAW viewers consume the same session gain. Ordinary
  non-RAW images are not transformed by this control in P3-B.
- At 1×, the viewer reuses `ImageDocument.preview` and does not schedule another
  full-frame gain render.
- Gain >1 preview regeneration uses resident native source and the existing shared
  numerical `QThreadPool`; source decode is not restarted.
- Viewer request/task/document/source/generation/gain identity rejects stale async
  results before presentation replacement.
- Hidden viewers release gain>1 viewer-local derived previews by restoring the
  canonical 1× document preview. When shown again they regenerate the current
  session gain.
- `RawDisplayState` outlives toolbar controls at QApplication scope; gain-control
  signal connections use QObject receiver lifetime so deleted controls do not
  leave Python closures targeting dead C++ widgets.
- Display Gain `+` / `-` commands are presentation-scoped, not window-global. The
  shortcut owner is `central_stack` with `WidgetWithChildrenShortcut`, so the
  command is active only while focus is within the image-presentation subtree.
- Files and other sibling UI retain native key behavior. Files `+` / `-` must
  continue to expand/collapse folders whether RAW Gain is enabled or disabled.

### P3-B regression coverage

Coverage includes:

- RAW10/12/14 effective-full-scale display mapping;
- Black/White not becoming 1× display endpoints;
- preview equality when only `white_level` differs;
- generic anchor-affine equivalence and float32 scale/offset;
- generic `anchor=0` core behavior for Gray/RGB without UI activation;
- channel-view gain demonstrating an RGBA-compatible alpha-preserving structure;
- known-value Black-anchored RAW arithmetic and below-Black underflow prevention;
- final-only clipping;
- RGGB/GRBG/GBRG/BGGR CFA-specific Black anchors and unchanged native mosaics;
- schema-valid GRAY tuple Black through JSON-profile → RAW-document loading;
- native pixel/Statistics/Histogram/Line Profile/Split Channels values;
- same-bit and mixed-bit P3-A Difference independence;
- source generation/residency accounting independence;
- non-RAW presentation regression;
- Single/Multi View gain behavior, default 1×, session-only state, stale-gain
  rejection, and gain-control teardown lifetime;
- 6→2→6 hidden derived-preview release/regeneration;
- real `+` / `-` key routing in the viewer presentation surface;
- Files-tree `+` / `-` expand/collapse preservation with RAW Gain both enabled
  and disabled.

### P3-B exclusions retained

P3-B does **not** add:

- ordinary Gray/RGB/RGBA gain UI/runtime activation;
- demosaic;
- white balance;
- CCM/color-space conversion;
- gamma/tone mapping as a new product feature;
- optical-black estimation or automatic pedestal detection;
- a processed-RAW document or analysis mode;
- a new Difference domain;
- RAW profile management/suggestion;
- session persistence;
- Settings schema expansion;
- preload/residency policy redesign;
- installer/signing work;
- broad MainWindow/toolbar redesign.

Rapid large-RAW gain stepping may temporarily accumulate superseded running
full-frame work because numerical cancellation is advisory. Stale result rejection
keeps correctness intact. Coalescing, debounce, or cancellable/chunked rendering
remains profiling-driven optimization rather than a P3-B merge requirement.

## P3-C — RAW Visualization & Inspection Improvements + Display Gain Extension

P3-C must reuse the P3-B generic anchor-based display-gain core rather than
introducing an ordinary-image-specific gain algorithm. It must also reuse P3-B's
presentation-scoped keyboard-command policy rather than adding a second shortcut
owner.

### Committed ordinary-image Display Gain scope

- Extend viewer presentation gain to ordinary Gray and RGB documents.
- Ordinary Gray/RGB use `anchor=0`.
- Extend to RGBA with gain applied to RGB only and alpha preserved exactly.
- The feature name is **Display Gain** or **Gain**. Do not label it **Exposure**;
  the operation is an explicit digital viewer gain, not a camera-exposure model.
- Gain remains viewer presentation only. Native source, Statistics, Histogram,
  Line Profile, Difference, source residency, and cache identity remain unchanged.
- Preserve the 1× identity/fast path and deterministic final clipping.
- Keep expensive full-frame work off the UI thread and retain stale-result
  rejection if asynchronous rendering is required for ordinary images.
- Reuse the existing presentation-scoped `+` / `-` command layer. Files-tree
  native expand/collapse must remain unaffected.

Required P3-C tests include:

- 1× identity for Gray/RGB/RGBA;
- gain and clipping for Gray and RGB;
- RGBA RGB gain with unchanged alpha;
- source/generation unchanged across gain changes;
- Statistics/Histogram/Line Profile/Difference independence from Display Gain;
- Single/Multi View consistency and stale-result/lifecycle behavior as applicable;
- command/control synchronization;
- Files-tree `+` / `-` routing preservation while Display Gain is available.

### Additional RAW visualization scope

Candidate work remains:

- clearer RAW Gain/clipping presentation for engineering inspection;
- optional highlight/shadow clipping visualization where useful;
- improved native Bayer-channel/mosaic inspection;
- viewer affordances that remain explicitly display-only.

Do not change Statistics/Histogram/Line Profile/Difference domains merely because
the viewer presentation changes.

Demosaic is deferred unless the owner separately approves a coherent
processed-preview scope. Before implementing it, explicitly decide whether white
balance, CCM, tone/gamma, Black/White normalization, and analysis interactions
belong in the same feature. A bare demosaic that creates misleading color output
is not a P3-C requirement.

## P3-D — RAW Profile Management

Build the reusable profile workflow after RAW native/display semantics are stable.

Target areas:

- reusable profile storage/selection;
- clear profile identity/versioning;
- safe edit/duplicate/delete behavior if introduced;
- profile suggestion based on deterministic metadata/size evidence;
- no silent profile application when evidence is ambiguous;
- compatibility with existing JSON profile migration and exact-size policy.

## P3-E — Integration & Hardening

Close P3 over the completed Difference/display/RAW semantics.

- Cross-check native/normalized Difference and display-gain independence.
- Characterize representative Gray/RGB/RGBA/Bayer/RAW and bit-depth combinations.
- Preserve P2 residency/preload/diagnostics contracts.
- Verify Statistics/Histogram/Line Profile/Difference/Split Channels regressions.
- Complete Windows characterization and durable P3 documentation.
- Do not add unrelated workflow/session or deferred processed-RAW features as part
  of phase closure.

## Cross-phase invariants

P3 builds on, and must preserve unless explicitly redesigned:

- P2 settings schema v5 migration/future-schema safety;
- exact native decoded-source residency accounting and protected soft-budget LRU;
- independent Difference Map Cache budget ownership;
- `+1`, one-position, max-one preload with foreground priority;
- exact RUNNING preload promotion without duplicate decode;
- advisory cancellation plus token/generation/request stale-result authority;
- observation-only sanitized **Help > Copy Diagnostics**;
- idempotent identical Statistics/Histogram numerical requests;
- expensive I/O/numerics off the UI thread;
- source dtype/channel meaning explicit and overflow-safe arithmetic;
- native source remains recoverable and authoritative even when viewer-only
  presentation transforms are active;
- presentation shortcuts must not override native sibling-widget navigation unless
  explicitly decided and regression-covered.

A P3 slice may extend display metadata or explicit derived representations, but it
must not collapse source residency, Difference cache, previews, or future
processed RAW data into one ambiguous memory owner.

## Explicit P3 exclusions

Unless independently approved, P3 does not include:

- persistent comparison sessions;
- Recent Files/Folders;
- saved ROI management;
- arbitrary-angle line sampling;
- alpha overlay;
- remote IQA submission/service work;
- login/SSO/credential lifecycle;
- installer/signing/updater work;
- broad shortcut or MainWindow rewrite;
- speculative preload concurrency/resource-policy expansion;
- native C/C++ optimization without profiling evidence;
- demosaic, white balance, CCM, or tone/gamma processing merely to make RAW look
  camera-rendered.

## Validation policy

For runtime slices, focused tests and the full repository contract remain the
completion standard:

```powershell
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Execution agents must not claim these passed unless their output was actually
observed. Owner/local Windows validation passed on
`424144215b1df97c71a84ddca79a17bfccb1feef`. The final independent re-review
identified the shortcut-focus blocker after that validated head. Because the
follow-up changes production UI composition, tests, and durable docs, validation
must be run again on the final P3-B head before merge. The Chat implementation
agent did not execute those commands.

## P3 exit criteria

P3 is complete when:

- P3-A Gray/mixed-bit Difference semantics remain stable;
- native samples are authoritative and viewer display transforms cannot be
  confused with analysis-domain processing;
- the generic anchor-based Display Gain core is deterministic and shared by RAW
  and ordinary viewer presentation without duplicated semantics;
- RAW Black-anchored gain and ordinary anchor-zero gain remain regression-covered;
- RGBA Display Gain preserves alpha;
- Display Gain keyboard commands preserve sibling-widget native navigation;
- RAW visualization improvements remain explicitly display-only;
- reusable profile management/suggestion is deterministic and safe;
- existing P2 runtime/resource/diagnostic contracts remain stable;
- full automated and agreed Windows validation pass;
- durable docs describe the final Difference, Display Gain, and RAW domains
  without ambiguity.

Demosaic is not required for P3 completion under the current owner decision.

## Later roadmap after P3

- **P4 — Workflow & Session Productivity:** persistent comparison sessions,
  Recent Files/Folders, saved ROI manager, arbitrary-angle line sampling, alpha
  overlay, and broader productivity/export workflows.
- **P5 — Remote IQA Platform:** remote submission/results, server/job API, GPU
  worker, artifact/heatmap/result comparison.
- **P6 — Identity, Access & Remote Operations:** login/SSO, token lifecycle,
  permissions, and operational administration.
- **P7 — Release Engineering & Distribution:** PyInstaller 5.7 `onedir`, portable
  ZIP, Inno Setup, clean-PC smoke, signing, updater/release process.
