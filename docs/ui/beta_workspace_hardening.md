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

### Floating workspace windows

Docked Plots/IQA retain the existing `QDockWidget`, custom dock title controls, object
names, geometry settings, `saveState`/`restoreState`, and re-docking contract.

While floating, `QDockWidget.setFloating()` remains the sole docking/topology authority.
Beta policy removes the custom title widget so Qt uses its documented native floating
window decorations, then clears the visible floating window's transient-parent relation.
It deliberately does **not** rewrite `QWidget.windowFlags()`: Windows/PySide validation
showed that changing the window type flags can silently collapse a floating
`QDockWidget` back into docked/child topology. Re-docking restores the retained custom
dock title widget.

The intended Windows behavior remains normal workspace interaction: independent
z-order/task switching, monitor movement, native title-bar drag, Snap/drag-to-top
maximize, maximize/restore, and later re-docking. Exact Windows DWM/taskbar behavior is
a manual qualification item rather than something inferred from the Qt window-type bit
mask in offscreen tests.

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

Existing workspace, IQA, Display Gain, Difference, and session tests remain regression
coverage and must be included in normal repository validation.

## Windows manual Beta checklist

1. **Single monitor:** enter Two Image, open IQA, then resize through narrow/wide widths
   and common desktop heights; controls/text remain usable and the main window is not
   forced beyond the work area.
2. Resize Two Image continuously around the point where tile metadata becomes compact;
   verify there is no persistent flicker or resize/render oscillation.
3. Dock Plots at the bottom and resize the Viewer/Plots boundary; verify both remain
   simultaneously usable at a normal desktop height without requiring maximize.
4. Float Plots, move it to another monitor, drag the native title bar to the screen top
   and Snap regions, maximize/restore, then re-dock it.
5. Repeat the same float/move/Snap/maximize/restore/re-dock flow for IQA.
6. With three monitors, maximize Main Viewer, Plots, and IQA independently on monitors
   1/2/3 respectively.
7. Switch among Main/Plots/IQA using normal click/task switching and confirm no floating
   workspace is forced permanently above Main.
8. Toggle IQA from the toolbar and menu, then close/hide the dock; verify checked and
   visible states remain synchronized in both directions.

Also confirm the PR #59 behaviors above have not regressed during the same pass.
