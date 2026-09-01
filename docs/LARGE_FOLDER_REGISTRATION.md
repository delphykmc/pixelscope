# Large folder registration contract

Issue #70 WP-A hardens local registration without changing supported formats or source semantics.
RAW/YUV format expansion belongs to later work packages and is intentionally outside this contract.

## Production lifecycle

The production **Open Folder...** and local drag/drop paths share one registration controller:

```text
request
  -> Scanning…                         filesystem discovery worker; total unknown
  -> Registering N / Total             GUI-thread catalog/tree chunks; total known
  -> completion summary                selection semantics applied once
```

Discovery owns only filesystem work and runs in a dedicated single-thread registration pool. It does
not share the foreground image-load pool, speculative preload pool, or numerical/analysis pools.
Qt widget/model changes and canonical document registration remain on the GUI thread.

Repeated requests are serialized. Application close cancels the active discovery, clears queued and
scheduled registration ownership, rejects stale generation/task results, and waits only a bounded
shutdown grace period for the registration pool.

## Performance contract

Registration must not rely on threading to hide avoidable GUI cost.

- Generic image discovery performs one final natural sort instead of per-source sorting followed by
  another global sort.
- Folder discovery naturally sorts each folder once and deduplicates repeated folder requests before
  registration.
- Files-tree child insertion uses cached natural-sort keys with binary insertion rather than scanning
  every existing sibling and recomputing its key.
- Main-window folder-position membership uses the same binary-insertion principle in the production
  registration composition instead of sorting the complete folder list after every new document.
- Each GUI registration chunk suppresses intermediate tree paints and yields back to the event loop
  before the next chunk.

These changes preserve the existing natural ordering and duplicate-suppression authority. They do not
introduce eager image decoding.

## Preserved input semantics

- Folder input is registration-only: no Selected, Current Comparison Page, or presentation mutation.
- Explicit dropped files are registered after dropped folders and replace Selected with the explicit
  file set, as before.
- A path present both inside a dropped folder and as an explicit dropped file remains two logical
  registration operations so the folder can register unresolved RAW metadata first while the explicit
  file retains RAW-profile resolution/selection intent. Canonical path identity still prevents a
  duplicate catalog document.
- Registered folder RAW stays lazy. Folder registration does not start foreground load or speculative
  preload work.
- Recent Folder/Image history and Folder Display Tags continue through the production composition.

## Automated acceptance

Focused coverage is deterministic and checks ordering, duplicate suppression, single-sort discovery,
chunk progress lifecycle, worker/GUI thread separation, stale-result rejection, cancellation, close
safety, common Open Folder/drop behavior, and lazy-load/preload non-regression. No pass/fail criterion
uses elapsed registration time.

## Manual validation

On Windows, use representative local and network folders containing hundreds to thousands of supported
images and confirm:

1. **Scanning…** is visibly indeterminate and the window remains interactive.
2. After discovery, progress changes to **Registering N / Total** and advances in batches without a
   long frozen tree repaint.
3. Natural filename order and duplicate suppression match the pre-WP-A behavior.
4. Folder-only registration does not alter the current Selected/page/view state or eagerly decode the
   newly registered images.
5. Mixed folder + explicit-file drag/drop registers folder contents first and selects only the explicit
   files.
6. Closing PixelScope during scanning or registration exits safely without a late catalog mutation or
   shutdown hang.
