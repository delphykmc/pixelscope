# WP-A — Large Folder Registration Responsiveness

Tracking: GitHub Issue #70, WP-A only.
Baseline: `main@e4308fd4a54e3a3811fdd9fee74b97f349ae53e3`.
Branch: `feature/wp-a-large-folder-registration`.

## Scope

Harden registration of large supported-image folders while preserving the current `.png/.bmp/.jpg/
.jpeg/.raw` input semantics. WP-B, WP-C1, and WP-C2 RAW/YUV format changes are explicitly deferred.

## Root cause

The baseline performed filesystem discovery synchronously on the GUI thread, sorted discovered inputs
more than necessary, scanned existing Files-tree siblings for every insertion, re-sorted folder-position
membership after every item, and requested row repaint/state presentation per inserted item.

The first WP-A implementation moved discovery to a worker and added chunked GUI registration, but owner
manual validation exposed remaining hot-path work: an eager `dict.setdefault()` default rebuilt existing
folder sort keys per insertion, fresh folder membership still linearly scanned the growing document list,
and worker-resolved paths were repeatedly canonicalized again on the GUI thread. Folder Display Tag row
presentation and the Files Type `ResizeToContents` policy added further per-item/tree-wide work. The
result could still approach quadratic cost and could visibly starve the Windows event loop.

## Implementation

- [x] Add filesystem-only registration discovery with cooperative cancellation and preserved folder /
  explicit-file intent.
- [x] Use a dedicated max-one registration discovery pool, separate from load/preload/analysis pools.
- [x] Keep canonical document and Qt model mutation on the GUI thread.
- [x] Compute canonical path/folder identities and natural-sort keys in worker discovery and carry them
  into the trusted production async registration path.
- [x] Preserve generic synchronous/programmatic canonicalization fallback for arbitrary paths.
- [x] Replace eager sort-key cache initialization with explicit one-time initialization.
- [x] Add an O(1) companion folder document-ID set instead of linearly scanning the folder list for every
  fresh registration.
- [x] Reuse worker sort/folder metadata in Files-tree insertion instead of repeating GUI-thread resolve /
  natural-key work.
- [x] Coalesce Folder Display Tag folder-row refresh once per GUI registration slice.
- [x] Bound GUI work by both an item cap (default 16) and a small time budget (default 8 ms), yielding to
  the event loop when either boundary is reached.
- [x] Temporarily suspend the Files Type column `ResizeToContents` policy while registration mutates rows,
  then restore the prior mode on completion/cancel/error.
- [x] Move scanning/registering progress directly below the Files tree; keep completion/error summaries
  in the global status bar.
- [x] Serialize repeated requests; reject stale task/generation results; cancel and bounded-wait on close.
- [x] Preserve duplicate suppression, natural ordering, lazy load/preload, mixed drop, Recent history,
  Folder Display Tag, and selection semantics.

## Automated validation

Focused deterministic coverage now includes:

- single-sort discovery and registration-intent ordering;
- worker-computed canonical path/folder/sort metadata;
- controller sort-key call count guarding against O(N²) cache reconstruction;
- O(1) folder membership guarding against fresh-item list scans;
- no per-image `Path.resolve()` on the production composed async GUI registration path;
- Folder Display Tag folder-row refresh coalesced per registration slice;
- Files-local scanning/registering/idle progress and Type-header resize-mode restoration;
- bounded registration progress increments without using elapsed wall time as a pass/fail threshold;
- large natural ordering and duplicate folder re-registration;
- no folder-registration foreground load/preload ownership;
- discovery worker versus GUI registration thread boundary;
- Open Folder and mixed drag/drop common controller path;
- cancellation plus stale discovery-success rejection;
- application close while discovery is running;
- close after the first GUI registration slice, with later scheduled work rejected;
- cancellation after the first GUI registration slice, with the already-scheduled callback rejected;
- a second request queued behind an active request, proving non-interleaving and final selection ownership;
- production composition with Recent Folder/Image history recorded exactly once;
- production Folder Display Tag application to asynchronously registered documents and folder rows;
- folder-only asynchronous registration preserving Selected, Current Comparison Page, presentation,
  layout, and Active state under the production controller composition.

Full repository validation follows `docs/QUALITY.md`. Wall-clock timing is characterization only and is
not an automated acceptance gate. The repository has no GitHub Actions workflow available for this PR,
so pinned CPython 3.10 validation must be reported from an authoritative local environment before merge.

## Review status

The initial lifecycle/serialization and production-composition review blockers were addressed. Owner
manual Windows validation then rejected the first performance implementation because scanning/registering
still felt frozen and path-only registration remained unexpectedly slow. Independent reviewer
cross-check confirmed the remaining O(N²), repeated canonicalization, tag-row refresh, GUI-slice, and
progress-placement findings addressed by the latest performance-hardening commits.

The branch is therefore **not merge-ready until the new exact HEAD is revalidated locally and the same
large-folder Windows manual scenario is repeated successfully**.

## Manual validation required

Use the same representative Windows folder with hundreds/thousands of supported images used to expose
the regression, including network or slower storage when practical. Verify Files-local progress,
responsive interaction during scanning and registering, no white/unresponsive window state, materially
improved path-only registration time, natural order, duplicate behavior, unchanged current view for
folder-only input, lazy decoding, mixed-drop selection semantics, and safe close during both scanning
and registration.

## Deferred

All Issue #70 WP-B/WP-C1/WP-C2 RAW/YUV semantic work remains untouched until WP-A is independently
reviewed and merged.