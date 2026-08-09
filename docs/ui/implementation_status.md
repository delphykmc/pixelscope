# UI implementation status

Status: Current through P3-C merge baseline; P3-D unified input work is active.

## Current shell

- Main toolbar remains focused on layout/view/analysis controls rather than file
  opening.
- File menu owns **Open Images...** (`Ctrl+O`) and **Open Folders...**
  (`Ctrl+Shift+O`).
- There is no separate **Open RAW with Profile...** action.
- Empty Workspace exposes Open Images/Open Folders only in the truly-empty state.
- Files tree is the catalog/selection surface and keeps native Up/Down plus
  expand/collapse key behavior.
- Analysis panel contains Statistics and Difference. Plots contains Histogram and
  Line Profile with persistent dock/floating state.

## P3-D input UI contract

The UI now distinguishes:

```text
Registered -> Selected -> Presented -> Resident when required
```

- Files registration is not capped by six.
- Open Images is selection-oriented: all directly selected supported files are
  registered and selected.
- Open Folders is registration-oriented: multiple folders may be added without
  changing current selection or viewer presentation.
- The project-local Qt folder picker uses extended multi-directory selection,
  deterministic resolved-path deduplication, and no six-folder limit.
- Folder D&D is registration-only for any folder count; the old exactly-two-folder
  auto-comparison behavior is removed.
- Direct image-file D&D registers and selects those files.
- Mixed D&D selects only the explicit files while folder contents remain
  registration-only.
- A catalog with zero selected documents is a valid state and displays **Select an
  image from Files to view**.
- A truly empty workspace displays **Drop images or folders here**.

Folder registration does not invoke the selection/presentation lifecycle, so it
must not reset the current layout, active/primary state, ROI, Line Profile,
Difference presentation, Display Gain, or existing view state.

## RAW input UI

RAW and ordinary images share **Open Images...**. Direct RAW keeps deterministic
same-basename sidecar/profile resolution, editable fallback, warning on invalid
sidecar, and cancel-before-registration behavior.

Folder RAW is registered lazily. Registration stores the RAW path and any exact
sidecar path without immediately opening a sequence of profile dialogs. The RAW
Profile dialog is shown when foreground loading actually needs unresolved metadata.
Unresolved RAW is not started by speculative preload.

The dialog uses **Load Profile...** / **Save Profile...** terminology. JSON remains
the compatible profile format.

## Presentation and interaction status

- Auto / Single View / Multi View remain the layout selector.
- Presentation remains bounded by the existing one-to-six-tile geometry.
- Registration count and presentation capacity are independent.
- Shared cursor/zoom/pan, Ctrl+drag ROI, Shift+drag Line Profile, primary/focus
  ordering, and selected-set navigation remain active.
- PageUp/PageDown Folder Position derives only from currently selected documents,
  not from every registered folder.
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

## Validation state

P3-D tests now cover menu/action naming, multi-image registration/selection,
>6 direct registration, multi-folder registration/deduplication, folder/image/mixed
D&D intent, registered-but-unselected state, lazy RAW resolution, selected-folder-
only Folder Position, and preservation of presentation/runtime state during
folder-only registration.

Tests were not run by this Chat implementation agent. Owner/local Windows
validation is pending.
