# UI implementation status

Status: Current through P3-C merge baseline; P3-D unified input and Current Comparison Page work is active.

## Current shell

- Main toolbar remains focused on layout/view/analysis controls rather than file
  opening, with a compact Comparison Page affordance shown only for large Selected
  sets.
- File menu owns **Open Images...** (`Ctrl+O`) and **Open Folders...**
  (`Ctrl+Shift+O`).
- There is no separate **Open RAW with Profile...** action.
- Empty Workspace exposes Open Images/Open Folders only in the truly-empty state.
- Files tree is the catalog/selection surface and keeps native Up/Down plus
  expand/collapse key behavior.
- Analysis panel contains Statistics and Difference. Plots contains Histogram and
  Line Profile with persistent dock/floating state.

## P3-D ownership UI contract

The UI distinguishes:

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

- Files registration is not capped by six.
- Selected is an ordered logical comparison set and may exceed six.
- Current Comparison Page is a derived maximum-six working subset.
- `Analysis Working Set = Current Comparison Page`.
- Viewer slots are local `1..6` inside the current page.
- Open Images is selection-oriented: all directly selected supported files are
  registered and Selected.
- Open Folders is registration-oriented: multiple folders may be added without
  changing Selected, Current Comparison Page, or viewer presentation.
- The project-local Qt folder picker uses extended multi-directory selection,
  deterministic resolved-path deduplication, and no six-folder limit.
- Folder D&D is registration-only for any folder count; the old exactly-two-folder
  auto-comparison behavior is removed.
- Direct image-file D&D registers and selects those files.
- Mixed D&D selects only the explicit files while folder contents remain
  registration-only.
- A catalog with zero Selected documents is a valid state and displays **Select an
  image from Files to view**.
- A truly empty workspace displays **Drop images or folders here**.

Folder registration does not invoke the selection/presentation lifecycle, so it
does not reset the current layout, active/primary state, ROI, Line Profile,
Difference presentation, Display Gain, or existing view state.

## Current Comparison Page UI

Large logical selections (`Selected > 6`) expose compact Previous/Next Comparison
Page controls with the current Selected range, for example `7–12 of 15`.

- `Ctrl+Left` / `Ctrl+Right` moves one Comparison Page and does not wrap.
- `Left` / `Right` remains fine Previous/Next Selected Image navigation.
- `PageUp` / `PageDown` remains Folder Position only.
- Number keys `1..6` retain page-local slot meaning.
- Single View presents one active local slot while retaining full page context.
- Large-selection Multi View retains six-slot Grid 3x2 geometry; a short final page
  clears unused slots rather than reflowing geometry.
- Primary/focus ordering is page-local and does not change Selected ordering or page
  membership.
- When `Selected <= 6`, large-selection page controls are hidden and existing
  Auto/Single/Multi behavior is retained.
- When `Selected > 6`, Folder Position is unavailable rather than operating on only
  the current page.

## RAW input UI

RAW and ordinary images share **Open Images...**. Direct RAW keeps deterministic
same-basename sidecar/profile resolution, editable fallback, warning on invalid
sidecar, and cancel-before-registration behavior.

Folder RAW is registered lazily. An unresolved RAW outside the Current Comparison
Page does not prompt or decode merely because it is Selected. Foreground page entry
invokes RAW profile resolution when source is required. Within one foreground
attempt, Cancel suppresses immediate passive re-prompt and starts no worker; a
later explicit foreground action may retry. Unresolved RAW is not started by
speculative preload.

The dialog uses **Load Profile...** / **Save Profile...** terminology. JSON remains
the compatible profile format.

## Presentation and interaction status

- Auto / Single View / Multi View remain the layout selector.
- Current Comparison Page is bounded to six; registration/Selected counts are not.
- Shared cursor/zoom/pan, Ctrl+drag ROI, Shift+drag Line Profile, primary/focus
  ordering, and selected-set navigation remain active.
- Statistics, Histogram, Line Profile, selection-derived Difference inputs,
  page-load requirements, ROI/Line normalization, and generic source protection
  follow the same Current Comparison Page authority.
- PageUp/PageDown Folder Position derives only from one-to-six currently Selected
  documents, not from every registered folder.
- Split Channels remains available for supported RGB/RGBA/Bayer sources.

## Display Gain status

P3-C is complete as PR #25 at
`7f6bef73e6712f6a14a4d401820a915196e25da2`.

- One session-local Display Gain control owns 1×/2×/4×/8×/16×.
- Ordinary Gray/RGB and split RGB use anchor 0.
- RGBA gains RGB only and preserves alpha.
- RAW retains P3-B native 1× and Black-anchored gain semantics.
- Difference is excluded from general Display Gain.
- 1× reuses canonical preview; gain>1 is viewer-local async presentation.
- Native analysis, source generation/residency, and Difference cache identity are
  not changed by gain.

## Runtime/resource status

P3-D preserves P2 exact native-source accounting and protected soft-budget LRU.
Selected membership alone is not a generic protection owner for large selections.
Current Comparison Page plus correctness dependencies are protected; off-page
Selected sources may be evicted/reloaded. P2 preload remains +1 Folder Position
only; there is no Comparison Page preload system.

## Validation state

P3-D focused tests cover menu/input behavior, large Selected registration, derived
1–6 / 7–12 / final Comparison Pages, local slots, fine/coarse navigation,
partial-final-page clearing, page-authoritative analysis inputs, bounded residency
protection, Folder Position separation, lazy RAW cancel/retry behavior,
multi-folder registration/deduplication, D&D intent, registered-but-unselected
state, and folder-only preservation of presentation/runtime state.

Tests were not run by this Chat implementation agent. Owner/local Windows
validation is pending.
