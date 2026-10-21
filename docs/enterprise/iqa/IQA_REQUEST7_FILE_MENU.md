# Analysis Window file menu and hover layout — request 7

Status: integrated into `integration/iqa-seven-requests-20261020`; handoff-only, never PUBLIC `main`.
Scope: company-neutral Enterprise IQA Analysis Window. Does not implement file formats,
touch saved packages, cancel provider jobs or change host viewer selection.

## Observable contract

1. **Close IQA Result** (`Ctrl+W`, Analysis Window only) removes the selected
   result, its in-memory analysis state and derived spatial cache. The next
   combo entry becomes visible, or the previous entry if the closed result was
   last. Closing the final result returns to a fully empty analysis presentation.
   Both Clear ROI controls are disabled in the empty state, and stale ROI
   callbacks safely return without accessing removed scene overlays.
   The window stays open. No loader, writer, filesystem or job callback runs.
2. **Exit** closes the Analysis Window, retaining its normal manager-owned
   reopen lifecycle. It does not unload/delete a portable artifact or cancel
   jobs, and its action is distinct from closing a result.
3. **Contributed result file type:** optional `ResultFileType(description,
   suffix)` travels from `IqaWindowContribution` through
   `AnalysisWindowManager` to `install_file_handlers`. A real injected
   reader/writer can provide, for example, `ResultFileType("PixelScope IQA
   result", ".pxiqa")`. Open/Save filters derive from the type; Save As
   suggests a sanitized result-ID filename with the declared suffix and adds
   the suffix if the chosen filename has none. **After suffix normalization**,
   the window refuses any already-existing final destination (including an
   existing `name.pxiqa` when the dialog returned `name`). The saver is not
   called; the status message asks for a different filename. The actual
   injected writer must also enforce safe, race-resistant file publication.
   No metadata leaves the window, changes result identity, or implements
   portable serialization.
   Omitting the file type keeps the existing generic filter.
4. **Hover formatting integration:** `hover_fields.py` provides the system
   fixed-pitch font and `format_source_rgb_field(role, rgb, bit_depth=...)`
   with right-aligned RGB components and a full-width missing-source slot.
   Existing PR #201 `ReservedHoverPair` owns the **only** two permanent
   Status Bar widgets. Both receive the fixed-pitch font, and their widths
   are reserved once after source images have been loaded for each Result.
   The PR #195 producer still owns the 3-view guides, source RGB lookup,
   map sampling and roles; it emits the padded fields without ever calling
   `statusBar().showMessage` on hover, which leaves room for future PR #197
   transient reader/writer error messages. The full original hover readout
   is retained by the labels' tooltips even if the visual field is elided.

## Validation / integration

Focused native Qt tests in
`tests/enterprise/iqa/test_analysis_file_menu_request7.py` cover the
result selector's next/previous/empty behavior, menu/shortcut enablement,
file/job independence at the I/O callback boundary, Exit/reopen,
contribution-driven file dialog metadata, an in-flight spatial `Future`
that completes after close, and the fixed-pitch/padded RGB formatting helper.
The `Future` test explicitly closes, immediately reopens another result,
then delivers the old completion and also retries the old result ID. No old
cache or UI state may be restored. A full Enterprise IQA test run with Python 3.10/PySide6 6.4.2 is required
on the integrated branch; owner-local Windows visual validation remains
necessary for shortcut focus and native geometry/lifecycle behavior.


Integration remains under the four reserved Enterprise roots, never PUBLIC
`main`. Preserve PR #197's broad callback exception handling and bounded
`user_message` in `_open_from_dialog` / `_save_from_dialog` as the **next**
request is integrated. Add an integrated `.pxiqa` failure regression covering
both a short user-facing message and an unexpected `Exception` without
allowing Qt slot exceptions to escape. Result ID, mask, scientific values,
spatial statistics and exports are unchanged by presentation formatting.
