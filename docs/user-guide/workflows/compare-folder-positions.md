# Compare Folder Positions

Folder Position navigation is for comparing matching natural-order positions across registered folders.

## Build a folder-backed comparison

Select an image from a registered folder. To add a matching position from another registered folder, use the Files context menu **Compare same position with...**. PixelScope uses the selected image's natural-order ordinal, not just its filename.

The convenience shortcuts `Alt+PageUp` and `Alt+PageDown` add the same position from the nearest eligible previous or next registered folder when a valid target exists. They do not wrap and they do not calculate Difference automatically.

## Move the whole comparison

Press `PageUp` for the previous Folder Position or `PageDown` for the next. PixelScope plans the move for the selected folder-backed sources as one operation.

If every required source cannot move to the requested position, the operation is a no-op rather than a partial move. Direct-open files without folder-position context can therefore prevent an atomic folder-position move.

## Capacity

A Current Comparison Page contains at most six sources. Same-position add operations stop when the visible comparison capacity is reached.

## Troubleshooting keywords

**PageUp**, **PageDown**, **Alt+PageUp**, **Alt+PageDown**, **same position**, **short folder**, **direct-open file**, **no-op**.
