# Compare More Than Six Images

PixelScope separates the logical Selected set from the number of images that fit on one screen.

## Select a large comparison set

Select as many registered sources as the workflow requires. PixelScope keeps the ordered Selected set and presents it in **Comparison Pages** of up to six images each.

## Navigate pages

Use the Previous/Next Comparison Page controls. The page indicator shows which slice of the Selected set is currently visible. Page-local number keys `1` through `6` activate only the visible slots on that page.

Statistics, Histogram, and Line Profile follow the **Current Comparison Page**, not every Selected source across all pages at once. This keeps analysis bounded and makes the visible comparison set explicit.

## Identify sources with identical filenames

Source tiles automatically distinguish repeated filenames using the shortest
necessary parent-folder suffix, for example `base / chart.png` and
`noise / chart.png`. If their folder suffixes are also identical, PixelScope
uses more parent folders and, if necessary, a stable short source identifier.
This is a **display label**, not a new image, source path, or analysis identity.

Select **Tag** in a source tile header to set or clear the existing folder
**Display Tag**. The same operation is available from the Files folder context
menu under **Set Display Tag…** / **Clear Display Tag**. Tags apply to the
folder, are stored with existing application settings, and are restored on
restart. Changing or deleting a tag only changes names; it does not reload
images, change selected/primary/picked roles, or recalculate a Difference.
Long labels are shortened in the tile, with the full source path in its
tooltip. Statistics, Histogram, Line and Difference use the same resolved
source names. Analysis does not add the parent folder again to an already
resolved alias or tag.

## Preserve selection

Moving to another Comparison Page does not discard the larger Selected set. If you curate or save the comparison, confirm whether you intend to persist the entire Selected set or a reduced subset.

## Troubleshooting keywords

**more than six**, **Current Comparison Page**, **selected images missing**, **page 2**, **slot 1-6**.
