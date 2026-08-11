# PixelScope user guide

## Opening images and folders

Use **File > Open Images...** to open one or more supported images for comparison.
The opened files become the current logical Selected set. Direct image-file drag/drop
uses the same selection-oriented intent.

Use **File > Open Folder...** to register supported images from a folder without
replacing the current Selected set. Folder drag/drop is also registration-only.

RAW files use PixelScope's existing RAW Profile workflow. Folder-registered unresolved
RAW files can remain pending until they enter the foreground comparison page.

## Selected and Comparison Pages

Files selection is the logical comparison set. Selected may contain more than six
images.

PixelScope presents up to six Selected images at a time as the **Current Comparison
Page**. Use the page controls or Ctrl+Left/Ctrl+Right to move between pages. Left/Right
retains fine Selected-image navigation. PageUp/PageDown remains Folder Position
navigation.

Statistics, Histogram, Line Profile, page-derived Difference context, and foreground
source loading operate on the Current Comparison Page rather than all Selected.

## Temporary review/curation

In Multi View, use **Pick** on source tiles to mark temporary candidates. Picks can
span Comparison Pages.

The presentation row shows:

```text
Selected N | Clear Selection | Keep Selection
```

Here `Selected N` is the temporary Pick count, not the Files logical Selected count.

- **Clear Selection** clears temporary Picks only.
- **Keep Selection** replaces Files logical Selected with the picked images while
  preserving their original Selected ordering.
- Non-picked images remain Registered in Files.

Picks are temporary workflow state. They are not saved automatically and do not make
off-page sources stay decoded/resident.

## Saving a Comparison Set

Use **File > Save Comparison Set...** to save the current logical Selected comparison
set as a `.pixelscope` file.

Important: **Save Comparison Set saves logical Selected, not temporary Picks.**

If you have made Picks and want to save only that curated subset:

1. choose **Keep Selection**;
2. confirm Files now shows the intended logical Selected subset;
3. choose **File > Save Comparison Set...**.

A Comparison Set v1 stores the ordered Selected source paths plus minimal stable
comparison context: optional Active source, optional applicable Primary source,
layout mode, and already-resolved RAW profile data when available.

Saving does not force every Selected source to decode or become resident, and it does
not clear a temporary Pick Set. With no logical Selected, the command performs a
normal no-op and reports that there is nothing to save.

## Opening a Comparison Set

Use **File > Open Comparison Set...** and choose a `.pixelscope` file.

PixelScope validates the artifact first. It then reuses saved sources that are already
Registered and registers other available saved sources through the normal input path.
Existing Registered images outside the set are not deleted.

Logical Selected becomes the loadable saved members in the artifact's saved order.
PixelScope restores the saved Active source when available, derives the appropriate
Current Comparison Page from that position, restores an applicable page-local Primary,
and restores the saved stable layout mode.

Opening a Comparison Set changes logical Selected. Therefore any temporary Pick
workflow that was in progress is invalidated in the same way as another normal
Selected replacement.

### Missing files

Comparison Set v1 uses exact normalized absolute local paths. If some saved sources
were moved or deleted, PixelScope loads the sources that still exist in saved order
and reports the missing paths compactly.

If no saved source is loadable, the current workspace is left unchanged.

PixelScope v1 does not search disks for moved files, guess by filename/size, or repair
paths automatically.

### Invalid or newer artifacts

Malformed JSON, wrong artifact kind, invalid required fields, or an unsupported future
schema version is rejected before current workspace state is changed.

## RAW sources in a Comparison Set

If a RAW source already has a deterministic resolved RawProfile when the set is saved,
that profile is included so the source can reopen deterministically.

Saving does not prompt unresolved RAW just to populate the artifact. Such a RAW member
stores only its source reference. On reopen, it follows the normal lazy foreground
RAW Profile workflow when native pixels are actually required.

## Comparison Set privacy

`.pixelscope` files can contain **absolute local filesystem paths**. These paths may
reveal usernames, directory names, project names, or other local metadata. Inspect or
treat Comparison Set files appropriately before sharing them outside your environment.

No cloud sync or remote telemetry is part of P4-B.

## What a Comparison Set is not

A Comparison Set is not a full PixelScope application session. It does not restore or
save:

- the entire Registered catalog;
- current page offset as independent state;
- decoded source/cache/residency/preload state;
- temporary Picks;
- ROI or Line Profile selection;
- Plots/window/dock geometry inside the set;
- Display Gain;
- Recent history.

Those boundaries keep the artifact deterministic and focused on repeatable image-set
comparison.

## Layout and presentation

Layout modes remain **Auto**, **Single View**, and **Multi View**. Display Gain remains
presentation-only at the existing gain choices and is not part of a Comparison Set.

Difference, Statistics, Histogram, Line Profile, Split Channels, RAW native/display
semantics, and pixel inspection retain their existing P3 behavior.
