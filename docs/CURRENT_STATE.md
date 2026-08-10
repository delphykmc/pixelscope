# PixelScope current state

Snapshot date: 2026-08-10
Current merged baseline / P3-D PR #26 merge commit:
`b16ecc558ac24225e9ddfddfca4e48e37fde61ca`

## Merge baseline

- P1-D/P1-E/P1-F completed as PR #10–#12.
- P2-0 through P2-F completed as PR #13–#20; P2-F merged at
  `9c66629f6392971b8c52ac9dff27b16166cf9829`.
- P3-0 merged as PR #21.
- P3-A Difference Gray/mixed-bit support merged as PR #22.
- P3 roadmap replanning merged as PR #23.
- P3-B RAW Native & Display Semantics merged as PR #24.
- P3-C Display Gain generalization merged as PR #25.
- P3-D Unified Image Opening & RAW Profile Resolution merged as PR #26 at the
  baseline SHA above.

The active plan is [`exec-plans/active/next-phase.md`](exec-plans/active/next-phase.md).
P3-E is **Integration, Presentation UI Polish & Phase Hardening**. It adds no new
analysis semantics and keeps P3-D's ownership hierarchy authoritative.

## Workspace ownership model

P3-D/P3-E distinguish five runtime layers:

```text
Registered
    ↓ user selection
Selected
    ↓ derived page offset / fixed page size
Current Comparison Page
    ↓ viewer representation
Presented
    ↓ native-source lifecycle
Resident when required
```

- **Registered**: known to the Files workspace/catalog. No artificial six-item limit.
- **Selected**: ordered logical comparison set. It may contain more than six images.
- **Current Comparison Page**: derived from Selected ordering plus page offset with a
  fixed maximum of six images. It is not a duplicated document collection.
- **Presented**: viewer representation of that working page. Multi View presents the
  page; Single View presents one active page-local slot.
- **Resident**: decoded native source held under the separate P2 source-residency
  budget when current correctness requirements need it.

`Analysis Working Set = Current Comparison Page`.
Viewer slot numbers are always local `1..6` within the Current Comparison Page;
global Selected ordinal and viewer slot are distinct concepts.

Registration count, Selected count, current-page size, presentation capacity, and
resident-source ownership are independent concerns.

## Unified input policy

Supported image inputs are exactly:

```text
.png  .bmp  .jpg  .jpeg  .raw
```

The image picker filter is:

```text
Supported Images (*.png *.bmp *.jpg *.jpeg *.raw)
```

### Open Images...

Selection-oriented input:

- multi-file selection is supported;
- all supported selected files are registered;
- registered direct files become the current ordered Selected set;
- Selected may exceed six without loss;
- initial Current Comparison Page is the first six Selected images;
- ordinary and RAW files share this command;
- RAW follows the existing profile-resolution contract before direct-open
  registration.

There is no separate **Open RAW with Profile...** action.

### Open Folder...

Registration-oriented input:

- the native picker selects one existing directory per invocation;
- multiple folders remain supported through folder D&D / the registration API;
- multiple supplied directory paths are deduplicated and ordered deterministically;
- practical folder registration count is not limited to six;
- supported immediate contents are registered in Files;
- current Selected set, Current Comparison Page, and presentation do not change;
- no first image is automatically selected;
- no two-folder comparison group is created implicitly;
- empty/no-supported-image folders are skipped and reported compactly.

Folder-only registration preserves layout, active/primary document, ROI, Line
Profile selection, Difference presentation/cache, Display Gain, existing view
state, and source-residency ownership because it does not invoke the selection or
render lifecycle.

### Drag and drop

- dropped image files are registration + selection oriented, like Open Images;
- dropped folders are registration-only, like Open Folder registration;
- any folder count uses the same policy; there is no exactly-two-folder special case;
- mixed file + folder drop preserves both intents: explicit files become Selected
  while folder contents remain registered-only.

Unsupported files and standalone `.json` sidecars never become image documents.

## Registered but unselected state

`registered documents > 0` with `selected documents == 0` is a supported state.
The central workspace displays **Select an image from Files to view**. A truly
empty workspace instead displays **Drop images or folders here** with Open Images
and Open Folder actions.

## Current Comparison Page navigation

For `Selected <= 6`, Current Comparison Page equals Selected and existing production
behavior remains the baseline.

For `Selected > 6`:

- pages are derived in six-image chunks from Selected ordering;
- the presentation-control row above the image workspace shows Page status and
  selected range; previous/next controls remain present and disable at endpoints;
- `Ctrl+Left` / `Ctrl+Right` move one Comparison Page only while that direction is
  available; unavailable Ctrl+Arrow remains native to the focused control;
- `Left` / `Right` retain fine navigation across the complete ordered Selected set;
- crossing a page boundary with Left/Right automatically changes Current Comparison
  Page so the active image remains in context;
- number keys `1..6` address the local slot of the Current Comparison Page;
- coarse page navigation preserves the active local slot where possible and clamps
  it to the last available slot on a short final page;
- large-selection Multi View retains six-slot `Grid 3x2` geometry, so a short final
  page clears unused slots rather than changing page geometry;
- Single View displays one active image but its analysis/load context remains the
  full Current Comparison Page.

PageUp/PageDown are not reused for Comparison Page navigation.

## P3-E presentation-row integration

The production application composes the P3-D presentation row with a focused UI
polish layer; command/state ownership remains in `MainWindow` and Display Gain
remains owned by its existing session state.

Presentation row contract:

- Layout remains on the left with Auto / Single View / Multi View.
- Comparison Page uses compact programmatic high-DPI Previous/Next icons from the
  existing PixelScope icon infrastructure.
- Previous/Next are `QToolButton` controls with stable geometry, explicit disabled
  endpoint states, tooltips, accessible names/text, and `NoFocus` mouse-command
  behavior; Ctrl+Left/Ctrl+Right remain the keyboard command owners.
- Page index and Selected range remain fixed-width semantic labels, preventing
  endpoint or digit-count layout shift.
- Display Gain stays on the right at 1×/2×/4×/8×/16× and is viewer-only.
- existing `design_tokens.py` colors, spacing, control height, border, and disabled
  text conventions define command-bar styling and Windows dark-UI contrast.
- the row remains distinct from the Main toolbar and directly above the image
  workspace.

No Review Pick/Keep Picked workflow state is introduced in P3-E.

## RAW registration boundary

Direct RAW open/drop preserves the P3-D contract:

- exact same-basename sidecar → parse/validate under confirmation and exact/minimum
  size policy;
- no sidecar → editable RAW Profile dialog;
- invalid sidecar → warning then editable fallback;
- cancel → no erroneous direct-open RAW registration;
- multiple RAW files resolve independently.

Folder registration is lazy for RAW. The RAW path and deterministic same-basename
sidecar path can be registered as a pending document without showing a dialog or
decoding source. An unresolved RAW that is Selected but off-page remains logical
selection only: it is not prompted, decoded, or made resident merely because it is
Selected. Profile resolution occurs when it enters the foreground Current
Comparison Page and native source is required. Unresolved RAW is excluded from
speculative preload until a profile is resolved.

One foreground presentation attempt prompts an unresolved RAW at most once. Cancel
leaves it registered and pending, starts no worker, and passive rerenders do not
immediately reopen the dialog. A later explicit foreground action may retry.

No profile is inferred from file size or other weak evidence. The RAW dialog uses
**Load Profile...** / **Save Profile...** terminology. P3-D/P3-E add no global
Profile Library, profile CRUD manager, last-profile reuse, apply-to-all behavior,
size-only/fuzzy matching, sensor/Bayer inference, or Black/White estimation.

## Navigation and analysis baseline

- PageUp/PageDown Folder Position operates only on one-to-six currently Selected
  documents from distinct folders. Other registered folders do not participate.
- `Selected > 6` makes Folder Position unavailable; PageUp/PageDown are a no-op
  with compact status rather than partially moving only the Current Comparison Page.
- Left/Right navigates the complete Selected set; Up/Down remains Files-tree
  navigation.
- Statistics, Histogram, Line Profile, selection-derived Difference context, ROI
  normalization, current-page load completion, and local slot mapping all use the
  same Current Comparison Page authority.
- Feature-owned explicit Difference Image 1/Image 2 authority remains unchanged.
- ROI uses Ctrl+drag / Esc; Line Profile uses Shift+drag / Shift+Esc.
- Statistics, Histogram, Line Profile, Difference, and pixel inspection consume
  native source semantics rather than gained preview pixels. Split Channels derives
  a transient viewer-local R/G/B or R/Gr/Gb/B working set while Files selection and
  native analysis authority remain on the original Current Comparison Page source.
- Difference supports Gray, RGB/RGBA, and same-CFA Bayer with native/normalized
  domain rules established by P3-A.

## RAW and Display Gain baseline

Current RAW support includes unpacked uint8/uint16, MIPI RAW10/12/14, stride,
offset, endian/alignment, Gray/Bayer layout, JSON migration, same-path reload,
exact/minimum-size policy, and Black/White metadata.

Display Gain remains presentation-only:

```text
display = anchor + gain * (source - anchor)
```

- choices: 1×/2×/4×/8×/16×;
- ordinary Gray/RGB uses anchor 0;
- RGBA gains RGB only and preserves alpha;
- RAW 1× uses native effective full scale;
- RAW gain >1 uses `B + G * (X - B)` with existing Gray/Bayer Black rules;
- 1× reuses canonical preview;
- gain changes do not mutate source, analysis results, request identity, residency,
  or Difference.

P3-E adds regression coverage that a pure Display Gain change does not reissue
Statistics, Difference-input, or Line Profile document requests when the native
numerical working set is unchanged.

## Runtime/settings baseline

Settings schema remains version 5. P3-E adds no settings/schema migration and no
Settings-owned RAW profile collection.

Source residency remains exact native `source.nbytes` under P2 protected soft-budget
LRU semantics, with the P3-D large-selection refinement that **Selected alone is not
a protection owner**. The generic bounded protection authority is the Current
Comparison Page plus correctness dependencies such as foreground loads, promoted
foreground preload, and Difference dependencies. Selected-but-off-page resident
sources may therefore be evicted and normally reloaded when revisited.

Difference cache remains independent. Preload remains +1 Folder Position, max-one
dedicated worker, with running-preload promotion as established by P2. P3-E does
not add Comparison Page preloading. Diagnostics remain deterministic, bounded,
sanitized, and observation-only.

## Active P3 sequence

1. P3-A — Difference Gray / Mixed Bit-Depth Support — Complete — PR #22
2. P3-B — RAW Native & Display Semantics — Complete — PR #24
3. P3-C — Display Gain Extension — Complete — PR #25
4. P3-D — Unified Image Opening & RAW Profile Resolution — Complete — PR #26
5. P3-E — Integration, Presentation UI Polish & Phase Hardening — implemented on
   feature branch; owner/local validation, independent review, and merge pending

## Validation state

P3-D owner/local Windows validation PASS and independent review are complete, and
PR #26 is merged at `b16ecc558ac24225e9ddfddfca4e48e37fde61ca`.

P3-E adds focused deterministic coverage for presentation-row command semantics,
15-image first/middle/final endpoint states, 50-image page-bounded foreground
loading/protection, final short-page clearing, and presentation-only gain changes
without numerical analysis-request churn. Existing P3-A–P3-D and P2 regression
suites remain the authoritative cross-feature coverage for Difference domains, RAW
Black/CFA behavior, Split Channels, preload, eviction/reload, lazy RAW resolution,
Difference cache ownership, and request dedup.

**P3-E tests have not been run by the Chat implementation agent. Owner/local
Windows validation is pending. Independent review and merge are pending.**
