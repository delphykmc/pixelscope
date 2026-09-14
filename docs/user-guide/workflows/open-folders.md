# Open Folders

Use **Open Folder** to register a folder tree for browsing and repeated position-based comparison.

## Register a folder

1. Choose **File > Open Folder...** or press `Ctrl+Shift+O`.
2. Choose the root folder. The native folder picker selects one directory per invocation.
3. PixelScope discovers supported files recursively and shows them in natural order.
4. Select the sources you want to compare; folder registration itself does not replace your existing Selected set.

To register several folders in one operation, drag/drop the folders into PixelScope. Folder contents remain **registration-only**: registering folders does not implicitly select the first image, create a two-folder comparison, change the Current Comparison Page, or reset the current viewer/analysis state merely because registration occurred.

Large folder registration keeps discovery separate from foreground image loading. RAW-like entries can remain unresolved until a foreground action needs their profile, avoiding a profile dialog or decode for every registered RAW file.

## Mixed file and folder drops

When an operation contains both direct image files and folders, folder contents remain registration-only while the direct-file part follows the normal initial/additive selection rule described in [Open Images](open-images.md).

## Natural ordering

Folder Position uses natural filename ordering, so numeric filename components are compared numerically where possible. This makes sequences such as `image2` and `image10` behave as users normally expect.

## Compare matching positions

After selecting corresponding sources from different folders, use `PageUp`/`PageDown` to move the comparison together. See [Compare folder positions](compare-folder-positions.md).

## Troubleshooting keywords

**folder scan**, **registered not selected**, **recursive folder**, **PageUp**, **natural order**, **RAW dialog**, **drag multiple folders**.
