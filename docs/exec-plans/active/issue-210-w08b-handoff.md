# Issue #210 — W08b batch profile and native preview handoff

Status: **Draft / owner integration and independent review pending**.
Base: `841d19b39594933cb3ef2cd2b206802e80030c06` (merged W08a #215).
Owner: orchestration team owns `app/main_window.py`, `bootstrap.py`, command map and central registration wiring.
This PR does **not** modify W04 viewer/view-state modules or private Enterprise code.

## Components and typed entry points

- `io.input_profile_batch.preflight_input_profile_batch(paths, profile, *, existing, override_sidecars, override_registered, require_exact_raw_size)`:
  **read-only** per-source status, required bytes, file revision, prior interpretation ID and a deep-copied typed prior native profile snapshot. Rejects missing/nonregular, unknown extension, YUV layout/size mismatch, invalid RAW footprint, and silent sidecar/registered overrides. RAW allows documented trailing bytes unless exact-size setting is enabled; native YUV always requires exact bytes.
- `ui.input_profile_batch.InputProfileBatchDialog(window, paths, *, require_exact_raw_size)`:
  chooses **W08a Recent/Favorite** RAW/YUV interpretations; runs bounded-worker Preflight, displays per-file before/after native fields (including endian, bit alignment, packed bit order, CFA phase, black/white and stride), source size, sidecar origin/override, and status. A separate scrollable confirmation dialog shows the complete before/after record for every eligible source before explicit approval. Reports per-source partial outcomes; completed totals are retained and Cancel Pending is disabled after completion; offers non-authoritative native preview.
- `ui.input_profile_batch.CanonicalBatchProfileAdapter(window)`: typed `existing(paths)` and `commit_one(candidate) -> document_id`. Uses the existing `_register_inputs(..., resolve_raw_profiles=False)` for new sources and `_mark_document_for_reload` plus `_refresh_reopened_selected_documents` for existing sources. Preserves registered/selected/page/primary authorities. New/off-page sources are **not decoded** merely by application.
- `ui.input_profile_batch.BatchProfileController.preflight(...)` → `preflight_ready(epoch, candidates)` → `approve(epoch, candidates)` → `commit_progress(epoch, outcome)` → `commit_finished(result)`. Cancellation before first committed source does not mutate the workspace. After commit, result is **partial**, not transactional rollback.
- `ui.native_input_preview.NativeInputPreviewController.request(path, profile, generation)`, `cancel()`, `shutdown()`; `preview_ready(epoch, NativeInputPreview)`, `preview_failed(epoch, reason)`. Uses established `TaskWorker` and application-owned two-thread analysis pool; native decoder and presentation-only 256-pixel crop. The YUV full-native reader is gated at 128 MiB input size so oversized YUV sources cannot trigger unbounded full-read preview memory; applying the profile is still available. The controller invalidates the previous epoch on every request, cancel and shutdown; stale callbacks never publish. Preview arrays are not submitted to native numeric consumers.

## Orchestrator-only minimal wiring suggestion

```python
# App action creation should be done in the owner-owned MainWindow/bootstrap.
# Do not hook/replace MainWindow methods at runtime.
def open_batch_profiles(self) -> None:
    paths = tuple(
        document.source_path for document in self.selected_documents
        if document.source_path is not None
    )
    # Optionally use explicitly chosen registered catalog paths rather than
    # Selected; never change selection merely to show the dialog.
    if not paths:
        return
    dialog = InputProfileBatchDialog(
        self, paths,
        require_exact_raw_size=self.application_settings.require_exact_raw_file_size,
    )
    dialog.exec()
```

The owner must select the actual source picker/action and decide whether the command targets `Registered` or `Selected`. The helper is not installed in bootstrap by this branch. If a source was changed externally between preflight and commit, the adapter rejects it and requests a fresh approval. It never modifies source files or JSON/imgprops.

## Review-driven corrections (PR #217)

- P1: per-file **typed old-profile snapshot**, complete field-by-field before/after disclosure and JSON/imgprops override in the preflight table, details panel and mandatory approval dialog. No hash-only comparison.
- P2: the final batch result persists after successful or interrupted commit; Cancel Pending is disabled after completion and cannot rewrite totals to “no changes made”.
- Regression: actual `InputProfileBatchDialog` tests cover endian-only, Bayer-pattern-only, sidecar override, and 4-file apply → finish → cancel.

## Validation gates

New focused tests:

```text
tests/unit/test_w08b_input_profile_batch.py
tests/ui/test_w08b_batch_preview.py
```

The owner must additionally run the existing W08a RAW/YUV library/dialog suites, legacy RAW10/12/14, native YUV444/422/420 reader/numerical contracts, source reload-generation/cache, selected/page/primary behavior, lifecycle under normal GC on Windows, and the full local suite. All tests not actually run remain **NOT RUN**, irrespective of test code presence or hosted workflow status.

## Boundaries and residual risks

- A file-size match is not proof of endian, CFA, packing or source content identity.
- Preview uses the existing native YUV reader for files up to **128 MiB**, still loading the full byte payload before cropping. The cap bounds source-file input size per YUV task, **not** total process RSS to a 256 × 256 crop. With two simultaneous workers the aggregate memory budget still needs Windows native validation. Larger YUV files show Preview Unavailable while remaining eligible for batch application.
- Preflight and commit recheck size/mtime/device/inode, but those advisory fields cannot detect a same-metadata content rewrite. Additional content fingerprinting is not claimed.
- Adding a user-facing command and exercising true owner Windows native lifecycle remain integration gates. MainWindow and W04-owned files are deliberately unchanged.
