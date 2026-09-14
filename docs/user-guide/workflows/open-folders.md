# Open Folders

Use **Open Folder** to register a folder tree for browsing and repeated position-based comparison.

## Register a folder

1. Choose **File > Open Folder...** or press `Ctrl+Shift+O`.
2. Choose the root folder.
3. PixelScope discovers supported files recursively and shows them in natural order.
4. Select the sources you want to compare; folder registration itself does not replace your existing Selected set.

Large folder registration is designed to keep discovery separate from foreground image loading. RAW-like entries can remain unresolved until a foreground action needs their profile.

## Natural ordering

Folder Position uses natural filename ordering, so numeric filename components are compared numerically where possible. This makes sequences such as `image2` and `image10` behave as users normally expect.

## Compare matching positions

After selecting corresponding sources from different folders, use `PageUp`/`PageDown` to move the comparison together. See [Compare folder positions](compare-folder-positions.md).

## Troubleshooting keywords

**folder scan**, **registered not selected**, **recursive folder**, **PageUp**, **natural order**, **RAW dialog**.
