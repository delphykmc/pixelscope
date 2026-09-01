# WP-A — Large Folder Registration Responsiveness

Tracking: GitHub Issue #70, WP-A only.
Baseline: `main@e4308fd4a54e3a3811fdd9fee74b97f349ae53e3`.
Branch: `feature/wp-a-large-folder-registration`.

## Scope

Harden registration of large supported-image folders while preserving the current `.png/.bmp/.jpg/
.jpeg/.raw` input semantics. WP-B, WP-C1, and WP-C2 RAW/YUV format changes are explicitly deferred.

## Root cause

The baseline performs filesystem discovery synchronously on the GUI thread, sorts discovered inputs
more than necessary, scans existing Files-tree siblings for every insertion, re-sorts folder-position
membership after every item, and requests row repaint/state presentation per inserted item. The
combined cost approaches quadratic behavior for large folders and blocks event processing.

## Implementation

- [x] Add filesystem-only registration discovery with cooperative cancellation and preserved folder /
  explicit-file intent.
- [x] Use a dedicated max-one registration discovery pool, separate from load/preload/analysis pools.
- [x] Keep canonical document and Qt model mutation on the GUI thread.
- [x] Register bounded chunks with one paint refresh per chunk and event-loop yield between chunks.
- [x] Replace sibling insertion scans and per-item folder-list sorting with cached-key binary insertion.
- [x] Expose indeterminate `Scanning…` followed by determinate `Registering N / Total` progress.
- [x] Serialize repeated requests; reject stale task/generation results; cancel and bounded-wait on close.
- [x] Preserve duplicate suppression, natural ordering, lazy load/preload, mixed drop, Recent history,
  Folder Display Tag, and selection semantics.

## Automated validation

Focused deterministic coverage now includes:

- single-sort discovery and registration-intent ordering;
- large natural ordering and duplicate folder re-registration;
- deterministic chunk progress sequence;
- no folder-registration foreground load/preload ownership;
- discovery worker versus GUI registration thread boundary;
- Open Folder and mixed drag/drop common controller path;
- cancellation plus stale discovery-success rejection;
- application close while discovery is running;
- close after the first GUI registration chunk, with later scheduled chunks rejected;
- cancellation after the first GUI registration chunk, with the already-scheduled callback rejected;
- a second request queued behind an active request, proving non-interleaving and final selection ownership;
- production composition with Recent Folder/Image history recorded exactly once;
- production Folder Display Tag application to asynchronously registered documents and folder rows;
- folder-only asynchronous registration preserving Selected, Current Comparison Page, presentation,
  layout, and Active state under the production controller composition;
- Files-tree natural-key call count to guard against sibling rescanning.

Full repository validation follows `docs/QUALITY.md`. Wall-clock timing is characterization only and is
not an acceptance gate. The repository has no GitHub Actions workflow for this branch, so pinned
CPython 3.10 validation must be reported from an authoritative local environment before merge.

## Manual validation required

Use a representative Windows folder with hundreds/thousands of supported images, including a network
or slower-storage case if available. Verify responsive window interaction, progress phase transition,
natural order, duplicate behavior, unchanged current view for folder-only input, lazy decoding, mixed
drop selection semantics, and safe close during both scanning and registration.

## Deferred

All Issue #70 WP-B/WP-C1/WP-C2 RAW/YUV semantic work remains untouched until WP-A is independently
reviewed and merged.
