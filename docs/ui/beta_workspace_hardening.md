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

Docked Plots/IQA retain the existing `QDockWidget`, custom dock title controls, object
names, geometry settings, `saveState`/`restoreState`, and drag-to-dock contract.

While floating, `QDockWidget.setFloating()` remains the sole docking/topology authority.
Beta policy removes the custom title widget so Qt uses native floating-window
non-client chrome, then clears the visible floating window's transient-parent relation.
It deliberately does **not** rewrite `QWidget.windowFlags()`: Windows/PySide validation
showed that changing the Qt window type can collapse floating topology and commonly
break drag re-docking.

On Windows only, after the dock is already floating, the existing native HWND frame is
promoted at the Win32 style layer to expose normal minimize, maximize, system-menu, and
close controls and to use app-window rather than tool-window presentation. Qt still
owns the `QDockWidget` floating state, so the native frame treatment does not replace
Qt's docking discovery or persistence authority. Re-docking restores the retained
custom dock title widget.

The docked maximize button intentionally means **float and maximize**. A docked panel
cannot meaningfully maximize independently inside `QMainWindow`; converting it to a
floating maximized workspace is therefore the explicit behavior. In floating native
mode there is no separate programmatic Dock button: users re-dock by dragging the
native title bar back to a valid dock area, preserving the visible docking preview.

The intended Windows behavior is normal workspace interaction: independent z-order and
task switching, monitor movement, native title-bar drag, Snap/drag-to-top maximize,
minimize/maximize/restore, and later drag re-docking. Exact DWM behavior remains a
manual qualification item.

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
- Plots/IQA remaining floating top-level `QDockWidget`s while native title chrome is
  active, transient-parent removal, maximize/restore where applicable, and custom-title
  restoration on re-dock;
- late hardening of already hidden/floating workspaces;
- Reset Workspace clearing both persisted and retained in-memory floating geometry.

`tests/ui/test_beta_workspace_persistence.py` additionally covers the production-order
restart path: save hidden/floating state, construct a new `MainWindow`, restore state,
and only then install Beta hardening. Hidden/floating topology must remain unchanged.

`tests/ui/test_beta_workspace_layout_allocation.py` covers bottom-corner ownership and
the shrinkable IQA detail/splitter policy. `tests/ui/test_beta_workspace_native_frame.py`
checks the Windows native style contract without replacing the `QDockWidget` topology.

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
4. Float Plots and confirm the native title bar exposes minimize, maximize/restore, and
   close; move it to another monitor, use Snap/drag-to-top, then drag it back until the
   dock target preview appears and re-dock it.
5. Repeat the same native-frame and drag re-dock flow for IQA.
6. From a docked state, use the custom maximize button and verify the documented
   float-and-maximize transition, then restore/re-dock normally.
7. With three monitors, maximize Main Viewer, Plots, and IQA independently on monitors
   1/2/3 respectively, and switch among them using normal click/task switching.
8. Toggle IQA from the toolbar and menu, then close/hide the dock; verify checked and
   visible states remain synchronized in both directions.

Also confirm the PR #59 behaviors above have not regressed during the same pass.
