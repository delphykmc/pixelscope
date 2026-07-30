# Architecture

## Boundaries and data flow

`io` decodes files into source arrays; `core.ImageDocument` owns those arrays,
metadata, immutable-display intent, caches, and evaluation results. `core`
performs display conversion, histogram/statistics, line-profile, and
overflow-safe difference math without Qt. `workers` executes expensive
I/O/numerics in `QThreadPool`. `ui` renders previews and emits lightweight image
coordinates. `app` owns documents, selection, generation checks, and window
lifecycle. `remote` defines versioned DTOs and clients independently of widgets.

The main layout is a horizontal splitter: a resizable left sidebar containing
Files and Analysis vertically, and the active single/2/4/6 viewer on the right.
Files is a `QTreeWidget` whose non-selectable roots are canonical parent
folders and whose selectable children are naturally sorted files. Its ordered
extended selection is the comparison set. A vertical splitter under the right
side gives the image viewer and line-profile plot a shared full width. Pixel
readout is a fixed-width permanent status-bar field. Application actions live
in standard File/Edit/Selection/View menus.

Source arrays retain their decoded dtype and channel order (gray, RGB, or
Bayer). Display transforms create uint8 previews; they never normalize source
arrays in place. Analysis promotes operands before subtraction or squared
error.

## Thread and document lifecycle

A task carries task, document, and generation IDs. Signals marshal results to
the UI thread, where request signatures are checked before application.
Cancellation is cooperative; shutdown marks active tasks cancelled and waits
for the pool. Registered paths start as lightweight pending documents and only
the current comparison page (up to six images) is decoded. The global pool is
capped at four threads to avoid concurrent 4K decodes exhausting memory.

Statistics/histograms are cached by document generation, integer half-open ROI
bounds, effective-bit-depth bin count, and histogram range. Line profiles are
cached by document generation and the inclusive horizontal line coordinates.
Changing the selection, ROI, or line starts a worker; stale results must match
the whole comparison request before display.

One Ctrl-drag creates an image-coordinate ROI. The application clamps it to the
common width/height of the selected loaded documents and propagates the same
offset and extent to every visible viewer. View ranges and cursor positions are
synchronized in multi-view mode.

View updates distinguish an intentional fit from content replacement. Space
toggle and multi-view drop additions reuse the current ViewBox range. Delayed
fit callbacks carry request tokens so an obsolete callback cannot reset a more
recent zoom. Range propagation is guarded against recursive callbacks.

The application keeps one naturally sorted document-ID list and current index
per normalized folder path. Pair navigation is valid for two to six selected
documents only when their folder keys are unique. All target indices are
validated before selection changes, so reaching the end of any folder leaves
the complete comparison set unchanged. Adding files re-finds the current
document identity after sorting instead of trusting an index that may have
shifted.

## Extension boundaries

RAW packing dispatch currently accepts unpacked u8/u16. MIPI RAW10/12/14 names
are reserved but rejected with a clear error; their unpackers can later replace
the reader boundary (and may become a native extension) without changing UI.
The REST job state machine is create, poll, result, or cancel/failure. The HTTP
client is synchronous by design and must be called from a worker.

All syntax and APIs target Python 3.10. Resource access will use package
resources/application data paths when packaging work begins.
