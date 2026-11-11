# Memo folder format and live ROI selection

Status: Active. Owner: ChatGPT-assisted, 2026-11-12.
Branch: `codex/memo-folder-live-switch-20261112`.

Owner scope: folder-root metadata-only `.pxmemo`, root HTML and relative `src/`
assets; old ZIP reading; opaque floating Memo and reliable dock icons; a conflict-free
View > Memo shortcut; cached live ROI selection without source reload or layout
reconstruction. Finish tests and create a PR, then suspend the computer. Do not
merge this PR or reinstate old wake/continuation timers.

Preserve source/numerics/Session/reset semantics and all owner untracked files,
including the newly created Memo_chart example and its report folder. Use explicit
owned Qt hooks, safe relative paths, digest validation and guarded publication.

Confirmed baseline defect: select_finding always verifies/restores; restore commit
calls `_mark_document_for_reload` even for registered sources. Floating/dock issues
were reported by the owner. The current native captures show opaque backgrounds
and readable painted icons; the exact old OS-specific transparency failure was
not independently reproduced before replacing the native chrome.

## Implementation and observed checks

- Metadata-only JSON map, relative assets, digest/directory inventories, bounded
  path/reparse checks, fsynced staged files, revision checks, install rollback and
  retained recovery copy if rollback fails. Folder move/open/save is covered.
- Old ZIP reads remain intact; a save migrates to a separate folder without
  replacing the old file. No binary PNG/CSV data is embedded in the new map.
- Resident source ID/generation matches use canonical shared ROI updates directly.
  Tests forbid registration, reload and `_render_selection` during repeated row
  switches, and assert unchanged source memory identity/generation.
- Memo uses an owned PlotsDockTitleBar, explicit opaque panel backgrounds and
  application-scoped Ctrl+Shift+M. The title controller is quiesced on shutdown.
- UI selection/format tests passed 23 in 18.29s; earlier broader native restore
  selection passed 35 in 26.81s. Folder integrity/recovery tests passed 10 in 2.54s
  before adding the final directory case. Final full validation remains pending.
- Actual synthetic-data folder-save and floating/dock captures passed 2 tests in
  3.85s; images 07/08/09 in the visual guide were inspected. Shortcut testing
  explicitly activates the Qt window, as existing repository keyboard tests do;
  no timeout increase or production focus bypass was added.

## Completion gates

Run final source/type/docs checks and normal-GC local full pytest on a committed
stable head, request independent read-only review, record exact results, create
the PR without merging, then register one sleep action with no wake timer or
continuation. Do not suspend while required verification is incomplete.

Changes: `io/memo_folder.py`, archive format dispatch, Memo coordinator/panel and
restore-controller live-selection hook; focused folder/format/chrome/native UI
tests; product, architecture, decisions, current state, shortcut/user/visual guide
and this record. No source/numerical/Session/packaging/dependency changes. Owner
untracked files (including the root chart Memo and old report folder) stay excluded.

Commits use configured owner identity and `Co-authored-by: ChatGPT <noreply@openai.com>`;
GitHub bodies/comments are ChatGPT-assisted. Physical DPI/multimonitor/SMB,
packaged execution and Enterprise remain unverified. Original-source absence is
supported, but broken/edited mapped evidence is explicitly rejected.

## Review remediation before final validation

Initial source checkpoint `7ee313b2` began a full run, which was interrupted before
completion to address confirmed findings; it is not a full PASS. A user folder
named `previous` collided with staging/backup names. Its regression failed before
the fix; staging now uses isolated fixed child paths, and previous/next/
presentation_report name cases pass.

Independent read-only review found that post-publication backup cleanup errors
could lose the committed revision in the UI. The writer now returns a typed
FolderSaveResult with committed revision and cleanup warning. First-save and
replacement cleanup-failure/retry tests passed; the coordinator carries that
warning without changing Saved into a failed save. Pure folder selection passed
16 tests in 5.69s after remediation. A new worker/UI regression checks Saved and
re-saving after the same warning. Final source review/full run are pending on the
next committed head; no PR has been created yet.
