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

That detached native relationship also requires an explicit shutdown boundary. Owner
validation reproduced a process hang when Main closed while either Plots or IQA was
floating. PixelScope now saves the user's dock/visibility state first, stops the owned
zero-delay geometry and transient-parent timers, then hides and re-docks managed floating
workspaces while Main's native backing store is still valid. The re-dock is teardown-only:
the saved floating and visible/hidden state is restored normally on the next launch.

### IQA toolbar authority

The main toolbar reuses the existing checkable **Show IQA Workspace** action. It adds no
second visibility boolean/action. Toolbar clicks, menu clicks, dock hide/close, and
visibility changes converge on the same QAction checked state.

### Pass 2 production-composed minimum-size contract

Pass 1 removed explicit local floors, but the final production composition still added
P4/P5 controls after the base widgets were constructed. Their intrinsic
`minimumSizeHint()` values accumulated through one-row layouts even though the outer
widgets reported `minimumWidth() == 0`. In the fontless offscreen audit environment this
left the full Files + Image + IQA window at a 2127 px minimum and caused a 1280 px resize
request to be rejected. The absolute number is not Windows qualification; the final-tree
allocation failure was the contract gap.

Pass 2 applies shrinkable policy to the **final composed tree**:

- Files remains the Qt-collapsible secondary pane and Image remains non-collapsible;
- long populated Files/Multi View labels do not establish an application-wide floor;
- Page status/range, Display Gain, Pick count, Clear, and Keep remain present. Page values
  paint-elide inside their compact group instead of extending into Gain/Pick, while their
  complete logical text remains synchronized in tooltip/accessibility metadata;
- Layout and Gain selectors respect current font/style content and native drop-down chrome
  instead of fixed compact pixel floors. Compact `Clear`/`Keep` labels likewise retain
  content-derived floors plus complete `Clear Selection`/`Keep Selection` accessibility
  and tooltip semantics; relevant font/style changes refresh those floors;
- the outer `RemoteIqaWorkspace`, workflow tabs, Setup/Jobs/Results pages, and composed
  Inspect/alias/result labels yield independently of the already-shrinkable inner Results
  widget;
- the PR #67 stacked Current Pair A/B presentation and RGB8 contract are preserved;
- no resize-event controller or second dock/splitter/geometry authority is introduced.

The automated reference is observable behavior: after production composition, empty and
populated long-name states accept 1920 x 1080 and the stricter 1280 x 720 logical resize
with IQA hidden or docked. These test viewports are qualification references, not new
pixel-perfect widget sizes. Actual Windows FHD/DPI behavior remains a manual gate.

Owner follow-up validation reported multi-monitor movement and dock interactions working
as intended, but 200% DPI exposed Layout/Gain and Clear/Keep content clipping inside
aggressively shrinkable fixed floors. The DPI follow-up keeps the one existing
presentation-control authority, replaces those actionable fixed floors with current
font/style-derived floors, and does not retain the separately tested IQA `Preferred`
experiment because it produced no meaningful width-recovery improvement.

### Pass 2 compact Plots, status, and dialogs

Inactive `QTabWidget` pages contribute size hints, so a wide Line Profile controls row
previously forced the complete Plots dock even while Histogram was active. Histogram and
Line Profile now use one content-driven responsive layout: controls retain the original
single row whenever their live size hints fit, and reflow to the compact two-row grouping
only under constraint. Visible Reference controls participate in the fit calculation, and
the same widgets move between rows without changing their values, signals, or ownership.
One elastic context value is right-aligned in that same wide row. Histogram shows the
bounds carried by the completed results that own its visible series, not merely the newest
input request. A shared bounds string is used when all results agree; full-image results
with different dimensions list each image's bounds explicitly. A changed or failed
request clears both the old chart and its context until matching results complete. Line
Profile shows progress/errors and the selected endpoints. Context can occupy a later
compact row when constrained and paint-elides while keeping complete tooltip and
accessibility text. With no line, the header context is hidden; the plot-area hint remains
the sole empty instruction. Existing plot mode, channel, Reference, hover, and analysis
ownership is unchanged.

Histogram Bin selection participates in the same request authority before its debounce
timer starts. A change cancels the prior worker, installs the new request signature,
clears completion identity, and invalidates chart/context together. Thus a superseded
worker result cannot render against the selected Bin control, and rapid return to a
previously completed selection still follows the cache/render path instead of terminating
at a stale completed-signature check.

The structured status bar keeps complete filename and pixel-summary strings as its
logical label text while painting an elided representation inside the allocated width.
The complete value remains in tooltip/accessibility metadata. Long values therefore do
not replace coordinate/zoom/task ownership or establish a new main-window floor.

The RAW profile dialog no longer contradicts its content with a fixed 280 px width. Its
resizable body scrolls while the validation actions remain in a fixed reachable footer.
The Settings dialog removes the legacy 820 x 540 hard minimum and continues using its
existing scrollable pages/footer. RAW parsing/validation and Settings schema/save/reset
contracts are unchanged.

### Pass 2 IQA populated/stress readability

Small and normal Results keep all initial Scene Trend series. For a large result, the
existing attribute checklist remains the presentation authority while the initial view
enables at most 32 attribute-by-variant series. Users may explicitly enable more; the cap
does not reject or alter result data. Hover text covers the currently visible series,
Scene ticks are thinned to at most 12 including the first and last Scene, and an in-plot
variant legend reuses existing pyqtgraph markers.

The Overview hierarchy retains every attribute summary but materializes per-Scene child
rows only for the selected or expanded attribute. Child identity remains
`(attribute_id, scene_id)` for existing selection and P5-D Inspect integration. Server-
authored measurement values, Reference/comparison math, Scene selection, result schema,
and native Inspect authority are unchanged.

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
- ordered shutdown persistence, deferred-callback quiescence, and native-dock
  normalization before worker/Main teardown;
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

`tests/ui/test_beta_workspace_persistence.py` covers the production-order restart path
and visible/hidden/maximized/restored floating-state persistence across shutdown
normalization for both Plots and IQA.

`tests/ui/test_beta_workspace_layout_allocation.py` covers bottom-corner ownership,
shrinkable IQA detail/splitter policy, and the Qt-native horizontal contract: Files may
collapse while the Image workspace may not.

`tests/ui/test_p1e_plots_workspace.py` treats floating-title double-click as a re-dock
contract rather than the superseded maximize/restore contract.

`tests/ui/test_beta_pass2_workspace_resize.py` covers the final production composition,
FHD/compact logical resize acceptance, empty/populated long-name states, IQA hidden and
docked states, child containment/non-overlap, two-page navigation, and continued
Page/Display Gain/Pick/Clear/Keep access. The DPI follow-up adds 960 x 540 hidden-IQA and
1280 x 720 docked-IQA allocation, current content/style floors, compact command
accessibility, idempotent floor ownership, and post-composition font/style refresh
coverage. These are Qt metric/layout contracts, not a substitute for real Windows DPI
visual qualification.

`tests/ui/test_beta_pass2_component_resize.py` covers inactive Plots page hints,
single-row wide presentation, compact fallback, resize state preservation, complete
context tooltip/accessibility retention, full-image/ROI and heterogeneous completed
Histogram bounds, Line endpoints, empty-context hiding, RAW scroll/footer reachability,
and compact Settings page/footer access. Analysis request-identity coverage also verifies
that pending/error transitions cannot leave a stale Histogram/context pair visible.
The request-identity suite additionally covers a rapid `Auto → 1024 → Auto` round trip,
held old-worker result rejection, changed-Bin calculation, and return-to-cached-Bin
rendering.

`tests/ui/test_beta_pass2_iqa_stress.py` covers deterministic small, normal, and stress
result models; bounded initial series/hover/ticks; variant markers; checklist opt-in; and
lazy hierarchy Scene rows without elapsed-time thresholds. It also covers current
tooltip/accessibility metadata through loading, result, Reference/error, filter/trend,
Scene preview, and open-error transitions.

Actual title-bar drag/drop docking is a Windows manual gate because offscreen Qt tests do
not exercise the native move loop or docking target preview.

## Current owner-local unrelated/unknown failures

PR #67 recorded three pytest failures as unrelated/unknown rather than modifying them
unless later evidence tied them to that branch:

1. Bayer Line Profile hover: expected `Gr@1`, observed empty hover text.
2. Workflow-polish page-label width: observed 67 px versus the font-metric expression.
3. Difference single-view numeric shortcut: after showing the Difference document,
   `Key_2` did not switch to the second selected source document.

The third case was checked against this branch: the failing test constructs
`MainWindow()` directly and the numeric shortcut/ImageViewer path was unchanged by the
Beta hardening work. A speculative numeric-key fallback was reverted.

Pass 2 full validation on its implementation head observed 1058 passed, one Windows
directory-symlink privilege skip, and two failures. The Bayer `Gr@1` node is the first
protected exception above and was not changed. The other failure checks that a full
Folder Display Tag remains literally present inside the tile header's already-elided
paint label in the fontless offscreen environment. That exact node reproduces on the
Pass 2 base `main@0ccb8b867d4989fc87ca73a66ffe5b78a5239fa5` under the same environment,
so it is recorded as pre-existing/offscreen validation debt rather than hidden as a Pass
2 regression. Full Folder Tag identity remains present in the `ImageDocument`, Files,
Difference selectors, analysis, plot titles, and tile tooltip. No test or production
behavior was changed to manufacture a full-suite PASS.

### Owner-validation findings resolved in the Pass 2 fix loop

Owner Windows validation after the implementation head found three in-scope issues across
two follow-up rounds:

1. Plots displayed its constrained two-row controls even at normal wide widths.
2. Closing Main while Plots or IQA was floating could emit native `WM_DESTROY` / invalid
   `GetDC` diagnostics and leave the process running.
3. Line Profile duplicated empty guidance in a second header row, while Histogram lacked
   same-row context identifying the full-image or ROI bounds used for analysis.

Independent review also found that the compact Image Page group's children could overlap
Gain/Pick at 1280 x 720 and that dynamic IQA label metadata could remain stale. The fix
loop added responsive Plots layout, bounded/eliding Page metadata, owning IQA label
synchronization, the explicit floating-workspace shutdown boundary described above, and a
shared controls-left/context-right Plots header contract.

On the integrated fix, Windows-native workspace/component tests passed 9 tests. A bounded
native shutdown matrix covered docked Plots and Plots/IQA floating visible, hidden,
maximized, and restored states; all nine processes exited 0 in 0.64–0.67 seconds without
the watchdog or the reproduced native diagnostics. This is direct native lifecycle
evidence, but it does not replace the remaining interactive DPI/multi-monitor/dock-drag
owner checklist.

The final fix-loop full offscreen suite reported 1069 passed, one Windows
symlink-privilege skip, and the same two proven pre-existing failures in 360.00 seconds.
The workflow Page-reservation regression now asserts the bounded/eliding metadata contract
instead of the superseded fixed-width reservation.

After the additional Plots context-row follow-up, integrated affected validation reported
54 passed with only the protected Bayer `Gr@1` failure, Windows-native header/context
validation passed 13 tests, and the full offscreen suite remained 1069 passed, one skip,
and the same two pre-existing failures in 367.83 seconds.

The subsequent exact-head review found one result-ownership gap: new input bounds could
temporarily describe old visible Histogram series, and different-size full-image results
were summarized using only the first image. Histogram invalidation now clears chart and
context as one presentation, and successful rendering rebuilds the context solely from
the owning results. Direct fix coverage passed 19 tests; the broader ordered
Analysis/Plots/workflow set passed 71 tests, including persistence tests before workflow
tests to verify `QSettings` isolation. The post-fix full offscreen suite reported 1071
passed, one Windows symlink-privilege skip, and only the same two proven pre-existing
failures in 367.40 seconds. The direct fix set also passed 19 tests with the Windows-native
Qt backend in 8.37 seconds.

A further exact-head review found that Bin changes invalidated presentation before the
debounced request identity changed. Rapid return to Auto could therefore hit the stale
completed-signature fast path and leave Histogram blank, and a prior worker could still
render before the timer. Bin selection now synchronously replaces request authority and
cancels the prior worker. Direct lifecycle coverage passed 22 tests both offscreen and
Windows-native; the broader ordered set passed 74 tests. The full offscreen suite reported
1074 passed, one Windows symlink-privilege skip, and only the two established failures in
364.96 seconds.

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
15. On an FHD monitor at 100%, minimize the production window with populated long names
    in Files + Two Image + docked IQA. Confirm the complete application remains within the
    work area and the IQA divider can be enlarged/reduced without making Image inaccessible.
16. Repeat the constrained workspace check at 125%, 150%, and 200%. Record the Windows
    logical work area and any clipped/inaccessible control; offscreen logical-size tests
    are not a substitute.
17. Open a stress IQA Result, verify the initial Scene Trend is limited and readable,
    enable additional attributes explicitly, expand multiple attribute summaries, and
    confirm Scene selection/Inspect still identifies the correct Scene.
18. Give Histogram and Line Profile ample width and confirm each control surface uses one
    row, with controls left and Histogram bounds / Line endpoints right-aligned. Confirm
    full-image and ROI bounds, then clear the line and verify its header context disappears
    while the plot hint remains. Narrow the dock until the compact fallback appears, then
    widen it and confirm control values, Reference choice, channel toggles, and plot content
    are preserved.
19. Exit PixelScope independently with Plots and IQA floating in visible, hidden,
    maximized, and restored states. Confirm the process returns control without native
    `WM_DESTROY`/`GetDC` diagnostics, then relaunch and confirm the saved topology and
    visibility are restored.

Also confirm the PR #59 behaviors above have not regressed during the same pass.
