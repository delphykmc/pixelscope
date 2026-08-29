# Beta workspace hardening

This note records the local desktop UI/window contract for Beta qualification. It does
not change PixelScope source, numerical, session, cache, residency, or Remote IQA
measurement/API authority. It does clarify the currently qualified Remote IQA client
submission domain as decoded RGB8 (`H×W×3`, `uint8`) only; no normalization/conversion
path is added.

## Scope

The hardening applies to the existing Main Viewer, Plots `QDockWidget`, IQA
`QDockWidget`, main splitter, and existing tile headers. Production Remote IQA
server/GPU/SSO integration is outside this UI qualification boundary.

PR #59 behavior is baseline, not new scope here:

- Primary changes under Display Gain do not flash/re-render unnecessarily;
- Folder Tag is display-only identity;
- cached Difference toolbar reactivation follows the established pair lifecycle.

## Root causes and policy

### Horizontal Files + Image + IQA

The central sidebar carried a blanket 320 px minimum while IQA also contributed
intrinsic widths from controls and long labels. Those independent minimums accumulated
at the `QMainWindow` level.

Beta policy removes the blanket sidebar floor, lets IQA labels/controls shrink or wrap,
and removes the legacy 230 px Scene attribute-list maximum.

Horizontal allocation intentionally remains Qt-native rather than introducing a custom
three-pane resize controller. The actual hierarchy is:

```text
QMainWindow
|- CentralWidget
|  `- QSplitter
|     |- Files
|     `- Image workspace
`- IQA QDockWidget
```

Therefore:

- dragging the Files/Image splitter is owned by `QSplitter` and adjusts those two panes;
- dragging the IQA dock divider is owned by `QMainWindow`/`QDockWidget` and resizes the
  central area against IQA;
- Files is a secondary splitter pane and remains collapsible using Qt's built-in
  collapse/restore behavior;
- the Image workspace is the primary surface and is explicitly non-collapsible;
- no custom mouse handling, collapse threshold, or IQA-resize Files-width restoration is
  installed.

This keeps the layout predictable and avoids replacing Qt's native splitter/dock
allocation semantics with another state authority.

### Docked IQA Current Pair width and qualified input domain

The P5-C Current Pair presentation previously placed the complete A/B pair summary and
Submit button on one horizontal row. With long filenames that row could dominate the IQA
`minimumSizeHint()` and make the total Files + Image + IQA desktop width unnecessarily
large.

The Beta presentation now mirrors the Folder Pair structure:

```text
Current Pair
A  reference_name.png
B  candidate_name.png
OK · RGB8 · 1920×1080                        Submit Pair
```

- A and B use separate rows;
- filename labels may yield horizontally and retain the complete filename in their
  tooltip, so filename length does not establish the dock minimum width;
- the third row uses the space corresponding to Folder Pair validation for an immediate
  Current Pair eligibility status, with Submit Pair at the right;
- Current Pair requires two native remote-eligible inputs that are already decoded as
  exactly `H×W×3` RGB with 8-bit / `uint8` samples;
- A/B original width/height must match;
- PixelScope does not silently convert GRAY/RGBA/RAW/RGB16, drop alpha, normalize higher
  bit depth, demosaic, tone-map, or resize an unsupported Current Pair merely to submit it;
- supported file extensions may differ when both decoded sources satisfy the same RGB8
  capability; extension equality is not itself a requirement;
- the same RGB8/geometry helper is checked again immediately before Current Pair
  submission so the displayed state and submit path cannot diverge after a document
  change.

The compact statuses are `OK · RGB8 · <width>×<height>`,
`Blocked · RGB images required`, `Blocked · RGB8 required`, and
`Blocked · size mismatch`.

This is a deliberate clarification/tightening of the **qualified client input
capability**, not a Remote IQA schema/API or numerical-result contract change. The
semantic evaluated-source capability is also RGB8 for Folder Pair Scenes, but PR #67
does not rewrite the existing P5-C Folder transport/validation implementation.

The production server-native two-folder API/validation migration is explicitly deferred
to real server integration. At that point the server should own exhaustive folder
enumeration/count/pair checks, decode/RGB8 validation, and per-pair geometry validation;
PixelScope should avoid eager full-folder decode merely to duplicate server work. Long
Folder validation must remain asynchronous with visible preparation/validation progress
(indeterminate while total work is unknown, determinate once a total is known). The
durable authority and follow-up boundary are recorded in `docs/REMOTE_IQA_CONTRACT.md`.

### Interactive minimum-width probe

`scripts/probe_workspace_min_widths.py` is a development-only helper for choosing
reasonable minimum widths. It does not modify the production defaults or normal
QSettings namespace.

Example:

```powershell
.\.venv\Scripts\python.exe scripts\probe_workspace_min_widths.py `
    --files-min 220 `
    --image-min 280 `
    --iqa-min 260
```

Useful options:

- `--files-min`, `--image-min`, `--iqa-min`: temporary minimum widths;
- `--files-width`, `--iqa-width`: optional repeatable starting widths;
- `--window-width`, `--window-height`: initial main-window size;
- `--with-sample-image`: compare the populated Image workspace with the default empty
  state;
- `--hide-iqa`: start without IQA.

The script uses the same production presentation composition as the normal application,
prints each pane's `minimumWidth()`, `minimumSizeHint().width()`, and `sizeHint().width()`,
and shows live Files/Image/IQA width/minimum/hint values in the status bar and console
while splitters are dragged. The probe intentionally changes only widget minimum widths;
it does not add custom splitter/dock event handling, so the observed allocation remains
the same Qt-native behavior used by production.

### Workspace title hierarchy

Files, Analysis, Plots, and IQA Results use the shared `title_background` surface
(`#1e2023`). This tone was chosen from the neutral region of the owner-provided active
Windows PixelScope caption and is intentionally darker than the main content surface.
The native Windows caption itself may contain OS-controlled tint/gradient and is not
reimplemented inside Qt.

The initial caption-tone pass exposed a second problem: the left sidebar headings were
still inside the original 4 px container inset, the Image presentation command bar used
its own height, and the QDockWidget title bar used the 28 px control height. Their lower
edges therefore landed on different Y coordinates even though their colors were related.

Beta now treats the upper workspace edge as one continuous chrome baseline:

- `WORKSPACE_CHROME_HEIGHT` is 34 px (`28 px` control height plus `3 px` top/bottom
  command-bar breathing room);
- Files and Analysis headings fill their container width rather than living inside the
  old 4 px outer inset;
- Files, Analysis, the Image presentation command bar, Plots, and IQA Results use the
  same 34 px chrome height where they form a top workspace edge;
- Files/Analysis use only a 1 px lower separator, not a framed box, so they do not read
  as editable text fields;
- the Image presentation bar and QDockWidget titles use the same 1 px separator token so
  the docked top line lands on one Y coordinate across Files -> Image -> IQA.

This is a visual/layout distinction only; dock, drag, resize, and topology behavior are
unchanged.

### Two Image resize stability

Display Gain workers are not viewport-size driven and already reject stale work by
request/generation identity. The geometry feedback risk is the tile header's responsive
metadata transition.

Beta policy makes `TileHeader` itself the single responsive authority, with a 32 px
compact/expanded hysteresis band and no immediate layout activation. No image render
request identity or source/display semantics change.

### Viewer + bottom Plots

Large workspace surfaces use flexible vertical sizing while fixed-height headers,
toolbar/status controls retain their established size. The central viewer can yield
height to the existing bottom Plots dock.

When IQA is docked left or right at the same time, the bottom dock owns both lower
`QMainWindow` corners. IQA plot/tree/preview surfaces no longer contribute fixed
minimum-height floors and their local splitters may collapse those detail regions.

### Floating workspace windows

Plots and IQA remain ordinary `QDockWidget`s in both docked and floating states.
`QDockWidget.setFloating()` remains the sole docking/topology authority, and the code
does not rewrite Qt window flags or native Windows HWND style bits.

The earlier native-frame experiment was rejected after owner-local Windows validation:
a floating dock could show a docking target preview, but after drop the window sometimes
remained floating and continued following the cursor. That native-frame mutation has
been removed.

PixelScope keeps the same custom title bar while docked and floating. Qt documents that
a `QDockWidget` with a custom title bar does not use native window decorations when it is
floated. That means PixelScope must provide the minimal visual frame that native chrome
would otherwise contribute.

The Beta floating-window frame is therefore intentionally small and presentation-only:

- docked Plots/IQA do not receive an extra outer frame;
- floating Plots/IQA receive a 1 px `TOKENS.border` outline around the complete
  `QDockWidget`;
- the caption remains the shared 34 px `title_background` surface with its lower
  separator;
- no drop shadow, native HWND mutation, custom resize hit testing, or window-flag rewrite
  is introduced.

This follows the same tool-window principle used by commercial IDE shells: docked tool
windows have a deliberate boundary, while floating tool windows need an explicit frame
against the document/workspace background.

Mouse press/move/release events not consumed by a control are ignored so they propagate
to `QDockWidget`, which owns dragging, docking discovery, the docking preview, and drop
completion.

Title controls are intentionally minimal:

- docked: **Float / Maximize / Close**;
- floating: **Dock / Maximize / Close**.

There is no Minimize control for a floating dock. Owner-local Windows validation showed
that minimizing this `QDockWidget` presentation produced an awkward title-only state and
did not add useful workflow value.

The docked Maximize button intentionally means **float and maximize**. Activating the
same control again restores and re-docks when the maximize operation originated from a
docked state. Floating double-click docks back into the remembered dock area. Dragging
the floating title bar back to a valid dock area remains the primary re-dock path.

The visible floating window's transient-parent relation is cleared after float so the
workspace is not forced permanently above Main, without altering `QDockWidget` topology.
Exact Windows taskbar/z-order behavior remains a manual qualification item.

### IQA toolbar authority

The main toolbar reuses the existing checkable **Show IQA Workspace** action. It adds no
second visibility boolean/action. Toolbar clicks, menu clicks, dock hide/close, and
visibility changes converge on the same QAction checked state.

## Focused automated coverage

`tests/ui/test_beta_workspace_hardening.py` covers:

- compact-mode hysteresis boundaries and document refresh inside the hysteresis band;
- removal of accumulated sidebar/IQA floors and legacy Scene attribute-list width cap;
- flexible vertical workspace policy;
- idempotent installation and single IQA QAction authority/order;
- toolbar/dock-close visibility synchronization;
- Plots/IQA retaining the PixelScope title controller and caption-tone title surface while
  floating;
- Dock/Float state synchronization, transient-parent removal, maximize/restore, and
  title-controller persistence on re-dock;
- late hardening of already hidden/floating workspaces;
- Reset Workspace clearing both persisted and retained in-memory floating geometry.

`tests/ui/test_beta_workspace_chrome.py` covers the visual frame contract directly:

- Files, Image presentation controls, and docked IQA title lower edges map to the same
  main-window Y coordinate;
- Files/Analysis and dock titles share the 34 px chrome height and separator token;
- floating Plots/IQA receive the explicit 1 px outer frame and remove it again on re-dock.

`tests/ui/test_p5c_setup_presentation.py` covers the stacked A/B Current Pair presentation,
yielding filename labels, compact RGB8 eligibility statuses, and Submit Pair enablement.
`tests/unit/test_iqa_current_pair_contract.py` freezes the qualified Current Pair domain:
matching RGB8 is accepted; non-RGB, size mismatch, mixed RGB8/RGB16, and matching
RGB16/RGB16 are rejected.

`tests/ui/test_beta_workspace_persistence.py` covers the production-order restart path.

`tests/ui/test_beta_workspace_layout_allocation.py` covers bottom-corner ownership,
shrinkable IQA detail/splitter policy, and the Qt-native horizontal contract: Files may
collapse while the Image workspace may not.

`tests/ui/test_p1e_plots_workspace.py` treats floating-title double-click as a re-dock
contract rather than the superseded maximize/restore contract.

Actual title-bar drag/drop docking is a Windows manual gate because offscreen Qt tests do
not exercise the native move loop or docking target preview.

## Current owner-local unrelated/unknown failures

During this Beta pass, three pytest failures are explicitly tracked as unrelated/unknown
rather than being modified under PR #67 unless later evidence ties them to this branch:

1. Bayer Line Profile hover: expected `Gr@1`, observed empty hover text.
2. Workflow-polish page-label width: observed 67 px versus the font-metric expression.
3. Difference single-view numeric shortcut: after showing the Difference document,
   `Key_2` did not switch to the second selected source document.

The third case was checked against this branch: the failing test constructs
`MainWindow()` directly and the numeric shortcut/ImageViewer path was unchanged by the
Beta hardening work. A speculative numeric-key fallback was reverted.

## Windows manual Beta checklist

1. **Single monitor:** enter Two Image, open IQA, then resize through narrow/wide widths
   and common desktop heights; controls/text remain usable and the main window is not
   forced beyond the work area.
2. Resize Two Image continuously around the tile-header compact transition; verify no
   persistent flicker or resize/render oscillation.
3. Dock Plots at the bottom while IQA is also docked. Drag the Viewer/Plots boundary
   upward and verify IQA detail/table regions compress so Plots can take useful height.
4. Drag the Files/Image splitter through its range. Files may collapse and restore using
   Qt's native splitter behavior; the Image workspace must not snap to zero width.
5. Drag the docked IQA divider through its range and confirm the central area/IQA sizing
   follows normal QMainWindow/QDockWidget behavior without a custom Files-width restore
   effect.
6. With two native images on the Current Comparison Page, verify IQA Current Pair shows A
   and B on separate rows. Matching RGB8 (`H×W×3`, `uint8`) inputs show
   `OK · RGB8 · <W>×<H>` and enable Submit Pair; non-RGB, RGB16, or size mismatch shows
   the corresponding Blocked status and disables Submit Pair. Confirm no automatic
   conversion/normalization/resize is performed. Long filenames must not force the IQA
   dock wider than its normal control minimum.
7. Use `scripts/probe_workspace_min_widths.py` to compare candidate Files/Image/IQA
   minimum widths in both empty and `--with-sample-image` states before fixing final
   values.
8. With Files + Image + docked IQA visible, confirm the lower separator of the Files
   heading, Image presentation bar, and IQA Results title forms one visually continuous
   horizontal baseline. Files/Analysis must not have an outer framed-box appearance.
9. Float Plots and IQA in turn. Confirm each floating window has a visible 1 px outer
   frame against the Image workspace even when their body colors are identical or very
   close, while the caption remains visibly distinct from the body.
10. For each floating workspace, verify Dock / Maximize / Close only. Drag to a valid
    docking preview, drop, and confirm immediate dock + mouse release; the floating-only
    outer frame must disappear after re-dock.
11. Repeat for IQA. Floating title double-click must dock.
12. From docked state, use Maximize and verify the documented float-and-maximize
    transition, then Restore and verify the dock returns to its remembered area.
13. With multiple monitors, move/maximize Main Viewer, Plots, and IQA independently and
    verify normal click/task switching without a workspace being permanently forced above
    Main.
14. Toggle IQA from the toolbar and menu, then close/hide the dock; verify checked and
    visible states remain synchronized in both directions.

Also confirm the PR #59 behaviors above have not regressed during the same pass.
