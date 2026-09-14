# Troubleshooting

Search this page using the symptom or concept shown in the UI.

## Difference is unavailable

Verify that both **Primary** and **Active** identify valid, distinct current-page sources. Check dimensions and source family. Bayer pairs must satisfy CFA compatibility. Native YUV pairs must use matching layout/subsampling; YUV-versus-non-YUV and mixed-subsampling Difference are not supported.

## PageUp or PageDown does nothing

Folder Position movement is atomic. If a selected participant has no previous/next position, is a direct-open file without folder-position context, or otherwise cannot participate, PixelScope does not partially move only some sources. Use registered folder-backed sources with matching positions.

## I cannot compare more than six images

The visible page has six slots, but Selected can be larger. Use the Previous/Next Comparison Page controls. Analysis follows the Current Comparison Page.

## My ROI disappeared

PixelScope clears an ROI when a new source/comparison context cannot represent that shared rectangle consistently. Re-enter exact X/Y/Width/Height in Statistics after confirming the new geometry.

## Line Profile is empty or needs reset

Open the Line Profile tab and `Shift+drag` a horizontal or vertical line. Use **Edit > Clear Line** or `Shift+Esc` while the Line Profile tab is current, then draw it again.

## RAW file will not open

Check width, height, storage format, bit depth, stride, offset, byte order/alignment, and Gray/Bayer interpretation. For MIPI packed input, verify the group-width constraint and minimum packed row size. A truncated file or stride smaller than the row payload is invalid. See the [RAW Guide](../formats/raw.md).

## What does stride mean?

Stride is the number of stored bytes from the start of one image row to the start of the next. It includes row padding. It is not necessarily the same as the number of decoded pixels or the minimum tightly packed row byte count.

## YUV size mismatch

Confirm dimensions and native layout. YUV422 requires even width; YUV420 requires even width and height. Native YUV currently uses the supported fixed 8-bit/tightly-packed/BT.601 Full contract. If the file actually contains Generic RAW data, choose the RAW interpretation instead.

## Remote IQA cannot submit

Remote IQA requires deployment configuration and eligible standard-image inputs. Local RAW/YUV viewing does not imply remote submission support. Verify the configured service/storage environment and use local PixelScope workflows independently if the service is unavailable.

## Search keywords

**Difference unavailable**, **Primary**, **Active**, **PageUp**, **PageDown**, **exact ROI**, **Shift+Esc**, **RAW14**, **stride**, **offset**, **YUV420**, **size mismatch**, **IQA Reference**, **Session**, **Comparison Set**.
