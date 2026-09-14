# Core Concepts

These terms describe the user-visible PixelScope workflow and are used consistently throughout the guide.

## Registered

A **Registered** source is known to PixelScope and appears in the Files workspace. Registering a large folder does not imply that every image is currently displayed or resident in memory.

## Selected

**Selected** is the ordered set of sources chosen for comparison. Selection may contain more than six images.

## Current Comparison Page

The **Current Comparison Page** is the page-sized window over Selected sources that is currently presented for comparison and analysis. A page contains at most six images. Statistics, Histogram, and Line Profile normally use this page as their analysis set.

## Active

**Active** is the source currently in focus. In Multi View it is typically the page-local slot you most recently activated. Number keys `1` through `6` select visible slots.

## Primary

**Primary** is an explicitly chosen reference role. Difference compares Primary with Active when both roles form a valid pair. Changing Active does not implicitly replace Primary.

## ROI

A **Region of Interest (ROI)** is a shared rectangular source-coordinate region used by analysis tools. Exact coordinates can be entered in Statistics.

## Difference

**Difference** is an explicitly calculated comparison between two compatible sources. Availability depends on source family, dimensions, channel semantics, and other format constraints.

## Folder Position

**Folder Position** is the natural-order ordinal of an image inside a registered folder. `PageUp` and `PageDown` move a valid multi-folder comparison to the previous or next matching position as one operation.

## IQA Reference

An **IQA Reference** is the reference source used when inspecting or submitting an Image Quality Assessment result/job. IQA availability can depend on deployment configuration; local image comparison does not require a remote IQA service.

## Related reference

See [Terminology](../reference/terminology.md) for a compact glossary and [Compare folder positions](../workflows/compare-folder-positions.md) for navigation rules.
