# Architecture

## Boundaries and data flow

`io` decodes files into source arrays. `core.ImageDocument` owns those arrays,
metadata, preview data, caches, and evaluation results. `core` performs display
conversion, Bayer plane handling, histogram/statistics, line-profile, and
overflow-safe difference math without Qt. `workers` executes expensive I/O and
numerics in `QThreadPool`. `ui` renders previews and emits lightweight image
coordinates. `app` owns documents, ordered selection, view state, generation
checks, and window lifecycle. `remote` defines versioned DTOs and clients
independently of widgets.

Source arrays retain decoded dtype and channel meaning: gray, RGB/RGBA, or
Bayer. Display transforms create uint8 previews without normalizing source
arrays in place. RGBA analysis intentionally ignores alpha. Difference and
squared-error paths promote operands before arithmetic.

## Workspace structure

The central horizontal splitter contains a resizable Files/Analysis sidebar and
the active Single or Multi View workspace. Files uses a two-level `QTreeWidget`:
non-selectable parent-folder roots and naturally sorted selectable files.
Extended ordered selection is the comparison set.

Histogram and Line Profile live in a bottom `QDockWidget` spanning the main
window. It can be hidden, floated, maximized, and restored without overlaying
the sidebar. The custom title bar draws consistent Float/Dock,
Maximize/Restore, and Hide icons using design-token colors. The status bar uses
separate fields for active metadata, coordinate, pixel value, zoom, and task
state.

Auto, Single View, and Multi View are public layout modes. Multi View maps two
items side by side, three to a smart focus layout, four to 2×2, and five/six to
3×2. Visual order is application state: promoting a reference moves it to the
first raster slot and shifts the previous reference and remaining documents
right. Logical selection badges remain stable.

## Thread and document lifecycle

Registered paths begin as lightweight pending documents. A dedicated load pool
uses at most two workers; the shared numerical pool uses at most four. This
limits concurrent 4K memory pressure. Six source images plus one derived
Difference document form the maximum resident comparison set.

Every task carries task, document, and generation IDs. Results return to the UI
thread and are applied only when their complete request signature is current.
Rapid navigation invalidates obsolete loads and coalesces analysis requests.
Statistics and histograms are cached by document generation, integer half-open
ROI, bit-depth bin specification, and range. Line profiles are cached by
generation and inclusive line coordinates.

## View lifecycle

One Ctrl-drag creates a common image-coordinate ROI, clamped to the selected
images. Alt-drag creates a shared horizontal or vertical line according to the
longer gesture axis. Cursor and view ranges synchronize across occupied tiles.

View updates distinguish layout fit from content replacement. An unchanged
preview is not uploaded again. If selection expands while a document is still
loading, the grid retains its refit request until every required preview is
ready and then fits synchronously once. This prevents 3→4→5 transitions from
preserving an invalid range. Ordinary navigation, display-only Diff updates,
and plot-dock resizing preserve zoom and offset. Recursive and layout-generated
range callbacks are guarded.

## Folder and Difference state

The application maintains one naturally sorted document-ID list and current
index per normalized folder path. Pair navigation is valid when selected files
come from unique folders. All target indices are validated before selection,
so an endpoint leaves the complete set unchanged.

Difference caches one order-independent native absolute map per source pair.
Channel selection, gain, threshold mask, display preview, and Full image/Active
ROI metrics derive from that map. Display-only changes update the Diff tile,
not every source tile. Six sources plus Diff force Single View until Diff is
disabled.

## Extension boundaries

RAW dispatch currently accepts unpacked u8/u16. MIPI RAW10/12/14 identifiers
are reserved but rejected clearly so future unpackers can replace the reader
boundary without changing UI. The REST job state machine is create, poll,
result, or cancel/failure; the synchronous HTTP client must run in a worker.

All syntax and APIs target CPython 3.10. Future packaged resource access must
work in exactly PyInstaller 5.7 `onedir` and must not depend on the source tree
or current working directory.
