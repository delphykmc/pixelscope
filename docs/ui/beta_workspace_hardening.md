# Beta workspace hardening

This note records the local desktop UI/window contract for Beta qualification. It does
not change PixelScope source, numerical, session, cache, residency, or Remote IQA
measurement/API authority.

## Scope

The hardening applies to the existing Main Viewer, Plots `QDockWidget`, IQA
`QDockWidget`, main splitter, and existing tile headers. Production Remote IQA
server/GPU/SSO integration is outside this UI qualification boundary.

PR #59 behavior is baseline, not new scope here:

- Primary changes under Display Gain do not flash/re-render unnecessarily;
- Folder Tag is display-only identity;
- cached Difference toolbar reactivation follows the established pair lifecycle.

## Root causes and policy

### Horizontal Two Image + IQA

The central sidebar carried a blanket 320 px minimum while IQA also contributed
intrinsic widths from two top-row combo boxes, long status/result labels, and the Scene
attribute list. Those independent minimums accumulated at the `QMainWindow` level.

Beta policy removes the blanket sidebar floor and lets child controls provide the
functional minimum. IQA long labels wrap, combo/list controls may shrink, and the
workspace uses a shrinkable horizontal size policy. This is not a new fixed narrow
width and does not change IQA data/model ownership.

### Two Image resize stability

Display Gain workers are not viewport-size driven and already reject stale work by
request/generation identity. The geometry feedback risk is the tile header's responsive
metadata transition: one 480 px threshold changed child visibility and immediately
activated layout, allowing a resize near that threshold to change its own size hint.

Beta policy makes `TileHeader` itself the single responsive authority, with a 32 px
compact/expanded hysteresis band and no immediate layout activation. Document refresh
and resize therefore use the same state transition rules. No image render request
identity or source/display semantics change.

### Viewer + bottom Plots

Large workspace surfaces use flexible vertical sizing while fixed-height headers,
toolbar/status controls retain their established size. The central viewer can yield
height to the existing bottom Plots dock instead of making Plot maximize the practical
only usable state.

When IQA is docked left or right at the same time, the bottom dock owns both lower
`QMainWindow` corners. IQA plot/tree/preview surfaces no longer contribute fixed
minimum-height floors and their local splitters may collapse those detail regions. This
allows the Viewer/Plots boundary to move substantially farther upward while keeping IQA
available above the bottom dock.

### Floating workspace windows

Plots and IQA remain ordinary `QDockWidget`s in both docked and floating states.
`QDockWidget.setFloating()` remains the sole docking/topology authority, and the code
does not rewrite Qt window flags or native Windows HWND style bits.

The earlier native-frame experiment was rejected after owner-local Windows validation:
a floating dock could show a docking target preview, but after drop the window sometimes
remained floating and continued following the cursor. The movement looked like a race
between Qt's native move/dock loop and the Win32 frame mutation. That native-frame
mutation has been removed.

PixelScope now keeps the same custom dark title bar while docked and floating. The title
bar follows Qt's documented custom-title contract: mouse press/move/release events that
are not handled by a title control are ignored so they propagate to `QDockWidget`, which
owns dragging, docking discovery, and the docking preview.

Title controls are state-specific but visually consistent:

- docked: **Float / Maximize / Close**;
- floating: **Dock / Minimize / Maximize / Close**.

The docked Maximize button intentionally means **float and maximize**, because a docked
child cannot independently maximize inside `QMainWindow`. Floating double-click docks
back into the remembered dock area. Dragging the floating title bar back to a valid dock
area remains the primary re-dock path and must preserve Qt's visible docking preview.

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
- removal of accumulated sidebar/IQA layout floors and flexible vertical policy;
- idempotent installation and single IQA QAction authority/order;
- toolbar/dock-close visibility synchronization;
- Plots/IQA retaining the PixelScope title controller while floating;
- floating-only minimize control, Dock/Float state synchronization, transient-parent
  removal, maximize/restore, and title-controller persistence on re-dock;
- late hardening of already hidden/floating workspaces;
- Reset Workspace clearing both persisted and retained in-memory floating geometry.

`tests/ui/test_beta_workspace_persistence.py` additionally covers the production-order
restart path: save hidden/floating state, construct a new `MainWindow`, restore state,
and only then install Beta hardening. Hidden/floating topology must remain unchanged.

`tests/ui/test_beta_workspace_layout_allocation.py` covers bottom-corner ownership and
the shrinkable IQA detail/splitter policy.

Actual title-bar drag/drop docking is a Windows manual gate because offscreen Qt tests do
not exercise the native move loop or docking target preview.

Existing workspace, IQA, Display Gain, Difference, and session tests remain regression
coverage and must be included in normal repository validation.

## Current owner-local unrelated/unknown failures

During this Beta pass, three pytest failures are explicitly tracked as unrelated/unknown
rather than being modified under PR #67 unless later evidence ties them to this branch:

1. Bayer Line Profile hover: expected `Gr@1`, observed empty hover text.
2. Workflow-polish page-label width: observed 67 px versus the font-metric expression.
3. Difference single-view numeric shortcut: after showing the Difference document,
   `Key_2` did not switch to the second selected source document.

The third case was checked against this branch: the failing test constructs
`MainWindow()` directly and the numeric shortcut/ImageViewer path was unchanged by the
Beta hardening work. A speculative numeric-key fallback was therefore reverted and
`src/pixelscope/ui/image_viewer.py` remains identical to the PR base.

## Windows manual Beta checklist

1. **Single monitor:** enter Two Image, open IQA, then resize through narrow/wide widths
   and common desktop heights; controls/text remain usable and the main window is not
   forced beyond the work area.
2. Resize Two Image continuously around the point where tile metadata becomes compact;
   verify there is no persistent flicker or resize/render oscillation.
3. Dock Plots at the bottom while IQA is also docked left/right. Drag the Viewer/Plots
   boundary upward and verify Plots can take substantial height while IQA detail/table
   regions compress rather than imposing a fixed vertical floor.
4. Float Plots. Confirm the title remains PixelScope dark style and exposes Dock,
   Minimize, Maximize/Restore, and Close. Drag it back until the docking target preview
   appears, drop it, and verify the mouse is released and the dock actually reattaches.
5. Repeat the same styled-title and drag re-dock flow for IQA.
6. From floating state, double-click the title and verify it docks normally. From a
   docked state, use Maximize and verify the documented float-and-maximize transition.
7. With multiple monitors, move/maximize Main Viewer, Plots, and IQA independently and
   verify normal click/task switching without a workspace being permanently forced above
   Main.
8. Toggle IQA from the toolbar and menu, then close/hide the dock; verify checked and
   visible states remain synchronized in both directions.

Also confirm the PR #59 behaviors above have not regressed during the same pass.
