# Terminology

## Active
The source currently in focus for page-local interaction and the comparison side used with Primary for Difference.

## Comparison Page
A page-sized slice of the ordered Selected set. The Current Comparison Page contains at most six sources.

## Comparison Set
A persisted reusable comparison/source-selection artifact, narrower than a full Session.

## Difference
An explicit comparison result between a compatible Primary/Active pair.

## Folder Position
The natural-order ordinal of a source within a registered folder, used by synchronized `PageUp`/`PageDown` navigation.

## IQA Reference
The reference source role used by the configured Image Quality Assessment workflow.

## Primary
An explicitly chosen reference role. Primary is not automatically replaced merely because another source becomes Active.

## Registered
Known to PixelScope and visible in the Files model. Registration does not imply current display or memory residency.

## ROI
Region of Interest: a shared rectangular analysis area in source/reference coordinates.

## Selected
The ordered logical comparison set. It can contain more than six sources.

## Session
A broader persisted resume artifact that can restore source identity plus applicable workspace/view/analysis state.
