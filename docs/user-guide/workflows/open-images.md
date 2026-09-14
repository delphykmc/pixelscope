# Open Images

Use **Open Images** when you want specific files to become the current ordered comparison selection.

## Open one or more files

1. Choose **File > Open Images...** or press `Ctrl+O`.
2. Select one or more supported files.
3. Confirm the file dialog.
4. PixelScope registers the supported sources and makes them the current ordered **Selected** set.
5. If more than six are selected, the initial Current Comparison Page is the first six; the remaining sources stay Selected on later pages.

Supported extensions are summarized in [Supported formats](../reference/supported-formats.md). RAW-like files may require interpretation metadata; see [RAW](../formats/raw.md) and [YUV](../formats/yuv.md).

## Drag and drop files

Direct-file drag and drop follows comparison intent rather than folder-registration intent:

- with no current Selected set, a dropped batch is registered/selected and starts on its first Comparison Page;
- with an existing Selected set, new direct files are appended without discarding the existing comparison, and PixelScope reveals the page containing the last newly added source;
- unsupported files and standalone metadata files are ignored rather than treated as images.

Dropping files into Image View follows the same initial/additive selection rule and can also participate in the viewer's Quick Compare behavior.

## Direct files and Folder Position

A directly opened file does not automatically have the registered-folder position semantics needed by `PageUp`/`PageDown`. For synchronized folder navigation, register the containing folders and build a folder-backed comparison.

## Troubleshooting keywords

**unsupported suffix**, **RAW profile**, **YUV interpretation**, **file size mismatch**, **direct-open file**, **drag and drop**.
