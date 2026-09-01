# Large folder registration contract

Issue #70 WP-A hardens local registration without changing supported formats or source semantics.
RAW/YUV format expansion belongs to later work packages and is intentionally outside this contract.

## Production lifecycle

The production **Open Folder...** and local drag/drop paths share one registration controller:

```text
request
  -> Scanning…                         filesystem discovery worker; total unknown
  -> Registering N / Total             GUI-thread catalog/tree slices; total known
  -> completion summary                selection semantics applied once
```

Discovery owns filesystem work and runs in a dedicated single-thread registration pool. It does not
share the foreground image-load pool, speculative preload pool, or numerical/analysis pools. Discovery
also computes the canonical path identity, canonical folder identity/path, and natural-sort key that
are trusted by the subsequent production GUI registration path. Qt widget/model changes and canonical
document registration remain on the GUI thread, but that GUI phase does not repeat filesystem
canonicalization for each discovered image.

Repeated requests are serialized. Application close cancels the active discovery, clears queued and
scheduled registration ownership, rejects stale generation/task results, and waits only a bounded
shutdown grace period for the registration pool.

## Performance contract

Registration must not rely on threading to hide avoidable GUI cost.

- Generic image discovery performs one final natural sort instead of per-source sorting followed by
  another global sort.
- Folder registration discovery computes each image's natural-sort key once and carries that key into
  GUI registration.
- Main-window folder-position membership keeps an O(1) companion document-ID set and cached sort-key
  list; it does not linearly scan the complete folder list or rebuild all existing sort keys per item.
- Files-tree child insertion reuses the worker-computed canonical folder and natural-sort metadata for
  the async production path instead of resolving the same source path again on the GUI thread.
- Folder Display Tag document labels remain per-document, while folder-row refresh is coalesced once
  per GUI registration slice rather than repeated for every image.
- GUI registration has both a hard item cap (default 16) and a small GUI-time budget (default 8 ms),
  yielding back to the event loop when either boundary is reached.
- The Files tree Type column temporarily stops `ResizeToContents` auto-measurement during registration
  and restores its prior resize mode once the request completes or is cancelled.
- Intermediate tree paints are suppressed only within each bounded GUI slice.

These changes preserve the existing natural ordering and duplicate-suppression authority. Generic
synchronous/programmatic paths retain their canonicalization fallback and are not allowed to trust
unverified path metadata. The registration path does not introduce eager image decoding.

## Progress UX

Registration progress is owned by the **Files** pane because it describes Files-tree population rather
than a global application task:

- `Scanning…`: indeterminate progress directly below the Files tree.
- `Registering N / Total`: determinate progress in the same location.
- completion, cancellation, or error: the Files progress row is hidden.
- the global status bar remains responsible for completion/error summary messages and its existing
  application status content.

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
worker metadata reuse, controller sort-key call count, O(1) folder membership, absence of per-image GUI
`Path.resolve()` on the composed async path, coalesced Folder Display Tag row refresh, Files-local
progress lifecycle, bounded progress increments, worker/GUI thread separation, stale-result rejection,
discovery cancellation, close/cancel after a GUI registration slice, queued-request serialization and
final selection ownership, production Recent history and Folder Display Tags, common Open Folder/drop
behavior, and lazy-load/preload non-regression. No pass/fail criterion uses measured elapsed wall time.

The executable acceptance gate remains the standard validation in `docs/QUALITY.md`. This repository
currently has no GitHub Actions workflow available for this PR, so focused/full pytest, Ruff, mypy,
pip, docs, and diff checks must be observed in the pinned CPython 3.10 environment before merge.

## Manual validation

On Windows, use representative local and network folders containing hundreds to thousands of supported
images and confirm:

1. **Scanning…** is visibly indeterminate below Files and the window remains interactive.
2. After discovery, progress changes to **Registering N / Total** and advances without a long frozen
   tree repaint or Windows white/unresponsive window state.
3. Registration time is reasonable for path-only population and no longer grows with the previous
   repeated per-item canonicalization/full-list work.
4. Natural filename order and duplicate suppression match the pre-WP-A behavior.
5. Folder-only registration does not alter the current Selected/page/view state or eagerly decode the
   newly registered images.
6. Mixed folder + explicit-file drag/drop registers folder contents first and selects only the explicit
   files.
7. Closing PixelScope during scanning or registration exits safely without a late catalog mutation or
   shutdown hang.