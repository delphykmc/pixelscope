# Execution plan: filesystem-free Recent startup

Status: Startup slice implemented; review pending; explicit-open follow-up remains  
Owner: ChatGPT-assisted  
Branch: codex/fix-recent-startup-20261118 (from main e6e2265a)  
Last updated: 2026-11-18

## Goal

The first window opens with stale/disconnected UNC Recent entries intact. Loading,
deduplicating and rendering optional history must not resolve or inspect those
paths. No owner settings or real network shares are changed for verification.

## Scope

- Replace MRU filesystem canonicalization with lexical absolute-path normalization
  across Images/Folders/Sessions, legacy fallback, record/stage/remove and Session
  history notification. Retain order, limits, case identity and stored JSON format.
- Verify repository operations with filesystem methods forbidden, and the production
  startup composition with guarded stale UNC paths and an event-loop heartbeat.
- Keep registration discovery's canonical source identities and stage_canonical
  unchanged. Record lexical history versus actual symlink discovery semantics.
- Explicit Recent Image Open already uses the registration worker. This startup
  slice does not redesign synchronous Recent Folder/Session execution or configured
  dialog-directory validation. Those secondary #242 requirements remain open;
  do not close the whole issue on a startup-only fix.
- No Memo PR241 changes, RAW-height repair, packaging, network settings or history
  clearing. No automatic merge is requested for this separate branch.

## Current state and invariants

`compose_main_window_presentation` installs Recent menus before `window.show()`.
`RecentEntriesRepository.load` calls `normalize_recent_path` and then
`recent_path_identity`, both reaching Path.resolve(strict=False). Missing-path
exception handling cannot prevent the OS network wait. Session history notification
also re-resolves before calling the MRU observer. Only discovered inputs require
filesystem canonicalization; passive history does not own source/selection state.

Target CPython3.10 x64, normal GC, fixed dependencies and existing Qt ownership.
Never replace this call with another stat/existence/network probe or clear history
to hide the defect. Legacy absolute entries remain readable and are not rewritten
merely by startup. Relative public-API paths become absolute lexically.

## Slices and validation

1. RED: pure repository path-probe guards, Windows UNC/drive lexical cases, and
   production startup/menu guard with stale Images/Folders/Sessions.
2. Correct core normalization and the Session history callback. Verify symlink
   alias identity remains lexical while worker-supplied canonical paths are retained.
3. Run recent-entry unit/UI, Open Images registration and relevant Session suites;
   tracked-Python Ruff/format, mypy, docs/strict MkDocs and diff checks. No full-suite
   or real disconnected-share/manual acceptance claim without actual evidence.
4. Update durable contracts, record exact results and remaining explicit-open work,
   commit with ChatGPT co-author, publish a separate reviewable PR if authorized.

## Progress

- 2026-11-18: confirmed startup resolve call chain on main e6e2265a. Isolated branch
  preserves PR241 and all owner-untracked files. Regression work starts before edits.

## Completion evidence

- Resumed the interrupted local edits on 2026-11-18. Core normalization uses
  `abspath`/platform lexical normalization rather than `Path.resolve`; Session
  history notification uses the same function. No source-discovery behavior changed.
- Added guarded repository/startup tests for stale UNC history, lexical dot/case
  duplicates, legacy fallback, record/stage/remove, canonical staging and the Session
  observer. Alias and canonical target remain distinct passive history identities.
- Native Windows CPython 3.10, normal GC:
  `.venv/Scripts/python.exe -m pytest -q tests/unit/test_recent_entries.py tests/ui/test_recent_startup.py tests/ui/test_p4c_recent_entries.py tests/ui/test_p4c_recent_entries_integration.py tests/ui/test_open_images_registration.py tests/ui/test_p4c_session_restore.py tests/ui/test_p4c_session_restore_overlay.py tests/ui/test_p4c_session_pr33_integration.py tests/ui/test_wp_c2_yuv_session.py tests/ui/test_p4b_comparison_set.py`
  returned **88 passed in 62.48s**, exit 0. Windows `0x8001010d` diagnostic appeared
  during the startup event loop; execution continued and passed. No claim that this
  native diagnostic is resolved. The alias-identity unit test was added afterward.
- Final unit selection:
  `.venv/Scripts/python.exe -m pytest -q tests/unit/test_recent_entries.py tests/unit/test_registration_discovery.py tests/unit/test_comparison_set.py`
  returned **38 passed in 1.03s**, exit 0.
- Initial test invocation referenced nonexistent `tests/ui/test_recent_entries.py`:
  no tests ran, exit 1. Corrected selection is recorded above.
- `$trackedPython = @(git ls-files '*.py')`; Ruff check and format check on
  `@trackedPython tests/ui/test_recent_startup.py`: exit 0, **411 files already
  formatted**. `mypy src`: **134 source files, no issues**, exit 0.
- `scripts/check_docs.py`: **Documentation contract passed**;
  `python -m mkdocs build --strict`: exit 0, built in **2.55s**;
  `git diff --check`: exit 0. Durable-doc diff is additive, with no deletions.
- Manual checks: code/call-site and diff review only. No real disconnected SMB,
  cold-start timing, physical first-paint or packaged acceptance was performed;
  simulated offline paths are guarded against filesystem probes instead. Existing
  owner settings and unrelated untracked artifacts were preserved.
- Full repository pytest and independent review were not run; this is a bounded
  Draft startup fix, not a merge-ready/full-suite claim. Folder/Session explicit-open
  checks and dialog-directory network access remain synchronous and require a
  separate bounded-worker design and lifecycle coverage. Keep #242 open.
- Attribution: owner Git identity `mc.kang <delphykmc@gmail.com>` with
  `Co-authored-by: ChatGPT <noreply@openai.com>` on the new commit; Draft PR body
  marked ChatGPT-assisted. Existing human commits are not rewritten.
