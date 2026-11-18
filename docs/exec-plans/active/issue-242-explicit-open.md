# Execution plan: responsive Recent Open and dialog directory preparation

Status: Active

Owner: ChatGPT-assisted

Branch: codex/fix-recent-open-20261118, from main 41ef9ff0

## Goal and scope

Recent Folder and Session commands must return control to the event loop before
network path checks, discovery or Session parsing. Configured/last-used dialog
directory validation must also run off the GUI thread. Preserve Missing Remove/Keep,
wrong-kind protection, folder-only selection, transactional Session restore, saved
RAW/YUV profiles and configured-directory fallback. Keep #242 open until validation.
Memo #241 merged first at 41ef9ff0; #240 is closed. RAW height repair (#236), packaging,
new settings, retries, and physical SMB qualification are outside this change.

## Design and invariants

- Recent Folder reuses the existing serialized registration pool and canonical
  metadata; add a typed folder check before discovery rather than stat on the GUI.
- Session preflight reads/validates the artifact and prepares source identities on
  one bounded, window-owned preparation pool. GUI commit consumes prepared records
  without re-resolving paths; synchronous open_from_path remains available for
  established programmatic callers. No worker callable retains a UI owner.
- The same bounded preparation owner validates dialog-directory candidates before
  native choosers are shown. Explicit continuations keep GUI work on the GUI thread.
- Cancellation/supersession immediately revoke result authority. At most one worker
  and one pending request are retained. Close defers final destruction until the
  owned pool drains, without blocking the GUI or interrupting an OS network call.
- No numerical, Session-schema, source dtype/stride, decoding, or dependency change.

## Slices and verification

1. Guard Recent Folder/Session filesystem calls by thread, hold workers with events,
   verify heartbeat, no workspace mutation on cancel/close and missing/wrong kind.
2. Add standalone Session preparation, a bounded owner, canonical registration
   consumption and typed Recent Folder dispatch.
3. Move configured/last-used dialog-directory checks to preparation with fallback,
   preserve export snapshots and reject stale continuations after close.
4. Run relevant Recent/Session/registration/settings/export/native lifecycle tests,
   tracked Ruff/format, mypy, docs/strict MkDocs, diff checks, and owner-local full
   validation for the changed worker lifetime. Preserve the accepted existing RAW
   failure separately; no clean full-suite claim unless actually observed.
5. Update durable contracts, record exact output and publish a separate PR. No
   automatic merge of this new implementation is assumed from #241/#243 approvals.

## Progress

- 2026-11-18: read production composition, registration and Session restore paths,
  source identity/cancellation contracts and associated tests before edits.

## Completion evidence

- Initial regression selection before edits: **3 failed in 9.04s**, showing GUI-thread
  Recent network stat and close unable to yield. Guarded delayed/cancel/close selection
  after correction: **3 passed in 3.68s**. Expanded bounded supersession and dialog
  cancel/fallback selection: **6 passed in 5.82s**. Later successful Session commit
  guard plus export selection: **23 passed in 14.57s**.
- One initial related run was interrupted because old synchronous Session mocks could
  leave a modal error during the new async path. Updated tests use prepared Session
  commit and await actual completion; assertions and timeouts are retained. Recheck
  Recent selection: **23 passed in 18.05s**.
- Broader workflow run: **87 passed, 1 failed in 43.54s**. The histogram export loop
  read the second output before asynchronous directory preparation completed. It now
  waits for the output file and retains numerical/selection assertions.
- Final focused command (ordinary Windows, normal GC):
  `python -m pytest -q --tb=short tests/unit/test_session_preparation.py tests/unit/test_recent_entries.py tests/unit/test_registration_discovery.py tests/unit/test_comparison_set.py tests/unit/test_architecture_boundaries.py tests/ui/test_recent_open_preparation.py tests/ui/test_recent_startup.py tests/ui/test_p4c_recent_entries.py tests/ui/test_p4c_recent_entries_integration.py tests/ui/test_open_images_registration.py tests/ui/test_settings_dialog.py tests/ui/test_p4b_comparison_set.py tests/ui/test_p4c_session_restore.py tests/ui/test_p4c_session_restore_overlay.py tests/ui/test_p4c_session_pr33_integration.py tests/ui/test_wp_c2_yuv_session.py tests/ui/test_p4e_analysis_export.py tests/ui/test_p4e_analysis_export_review_regressions.py tests/ui/test_p4e_analysis_productivity.py tests/ui/test_large_folder_registration.py tests/ui/test_large_folder_registration_composition.py tests/ui/test_large_folder_registration_lifecycle_review.py --junitxml=temp/issue242-focused-final.xml`
  returned **179 passed in 90.21s**, exit 0. Log uses matching `.log` basename and
  retains the nonterminating native `0x8001010d` diagnostic. Small late source changes
  reject submit after window close and remove the unused old synchronous Recent
  Session method; immutable-head full validation follows.
- Source/worker design: no extra Folder pool; a standalone registration-discovery
  callable replaces the prior bound method. Session/dialog pool is capped at one
  running task and one latest pending request; worker callables carry no UI owners.
  Definition-time chooser continuations keep original GUI/export work on GUI thread.
  No permanent compatibility shim, packaging or dependency changes.
- Full validation, final static/docs checks and PR publication are pending. Real
  disconnected SMB, packaged execution and physical first-paint timing are unverified.
  Existing RAW height failure is separately deferred with owner approval; #242 stays
  open until review/closeout. Commits use configured owner identity plus ChatGPT
  co-author; GitHub activity is marked ChatGPT-assisted. Owner artifacts are untouched.

## Review follow-up — 2026-11-18

Independent exact-head review of `81eeb122` found two P1 issues: an ignored close
confirmation could poison both worker owners, and prepared Session commit could
race active/queued registration. Remediation checks and caches a *positive* close
confirmation before either close filter revokes authority; a rejected prompt leaves
both worker owners usable. Accepted close awaits physical drainage of both pools.
Prepared Session revokes the active registration generation and queued requests,
then waits for the running discovery worker to finish before GUI mutation. Later
Image/Folder/Session operations invalidate the deferred restore's epoch. Recent
Folder remembers its last-used path only after successful discovery completion.
The Session wait timer uses a 100 ms interval only while a physically running
registration worker remains. A disconnected SMB kernel call cannot be safely killed;
window close stays pending until it returns (potentially indefinitely). No arbitrary
worker deletion or synchronous GUI wait is permitted. Physical disconnected-SMB,
packaged, and real-screen tests still require owner acceptance. No clean full-suite
PASS is claimed; the owner observed one RAW compact-height failure (tracked #236).

New close-veto, queued-registration, chunk interleaving, supersession, and MRU
regressions were added for Windows validation. This is an implementation update,
not an independent approval; PR #244 remains Draft until tested/reviewed.

### Exact-head re-review follow-up (2026-11-18)

Review of `98ad29fd` accepted the earlier two P1 corrections but found one new
reentrancy blocker: the `progress_changed("scanning")` callback can synchronously
revoke or close RegistrationController before `TaskWorker` is constructed. After
emitting the signal, the controller now rechecks the active generation and close
flag before constructing/starting any worker. Deterministic tests trigger both
Session restore and accepted close *inside* that scanning observer and assert no
stale worker or mutation follows. Registration close-drain polling is bounded to
100 ms while an uninterruptible OS call runs, tested with a held discovery
worker and a live GUI event-loop heartbeat. A blocked call can still delay close
indefinitely; this is an explicit lifetime-safety tradeoff, not a completed
physical disconnected-SMB acceptance test. New exact-head local validation and
independent re-review remain outstanding; keep PR Draft.
