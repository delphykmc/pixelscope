# Analysis Window file menu and hover layout — request 7

Status: feature branch `feat/iqa-analysis-file-menu-request-7`; handoff-only, never PUBLIC `main`.
Scope: company-neutral Enterprise IQA Analysis Window. Does not implement file formats,
touch saved packages, cancel provider jobs or change host viewer selection.

## Observable contract

1. **Close IQA Result** (`Ctrl+W`, Analysis Window only) removes the selected
   result, its in-memory analysis state and derived spatial cache. The next
   combo entry becomes visible, or the previous entry if the closed result was
   last. Closing the final result returns to a fully empty analysis presentation.
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
   the suffix if the chosen filename has none. No metadata leaves the
   window, changes result identity, or implements portable serialization.
   Omitting the file type keeps the existing generic filter.
4. **Hover formatting integration:** `hover_fields.py` provides a Qt system
   fixed-pitch font and `format_source_rgb_field(role, rgb, bit_depth=...)`
   with right-aligned RGB components and a full-width "unavailable" slot.
   The display helpers are independent of the source-pixel hover producer
   (request 3, PR #195) and the two `ReservedHoverReadout` labels (request 6,
   PR #201). At the coordinated integration head, apply the font to **both**
   labels before reserving their widths once per result, format both source
   slots with this helper, then feed the assembled RGB/map readout into the
   labels. Keep `statusBar().showMessage` for transient reader/writer errors
   (request 5, PR #197); do not overwrite those errors on unrelated hover
   or geometry updates. The widget-level wiring is **not** implemented on
   this standalone request-7 branch, because #195/#201 are not its ancestors.

## Validation / integration

Focused native Qt tests in
`tests/enterprise/iqa/test_analysis_file_menu_request7.py` cover the
result selector's next/previous/empty behavior, menu/shortcut enablement,
file/job independence at the I/O callback boundary, Exit/reopen,
contribution-driven file dialog metadata, an in-flight spatial `Future`
that completes after close, and the fixed-pitch/padded RGB formatting helper.
The `Future` test explicitly closes, immediately reopens another result,
then delivers the old completion and also retries the old result ID. No old
cache or UI state may be restored. Full native Windows validation
must be performed by the owner after request 3/6 integration. Hosted CI
static validation does not substitute for Qt runtime acceptance.

Integration must stay within the four reserved Enterprise roots and target
`handoff/enterprise-iqa-window`, not PUBLIC `main`. Reconcile concurrent
requests 1–6 before merging; review the same `analysis_window.py`
Open/Save exception handlers (request 5, PR #197), title/empty window
(request 1, PR #200), and hover/readout UI (requests 3 and 6, PRs
#195/#201) at the exact integrated head. Add an integrated `.pxiqa` reader/
writer failure regression exercising a short `user_message` and unexpected
`Exception` via the contributed file type. Keep PR #199 a draft until the
actual two labels are connected and native Qt Windows tests pass.
