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
4. **Hover formatting integration:** the requested fixed-pitch status fonts
   and absent-source field padding depend on the two hover status widgets
   introduced by separately developed requests 3 and 6. Integrate those
   source-level changes before calling this item complete; do not duplicate
   or fork a competing status readout in the handoff baseline.

## Validation / integration

Focused native Qt tests in
`tests/enterprise/iqa/test_analysis_file_menu_request7.py` cover the
result selector's next/previous/empty behavior, menu/shortcut enablement,
file/job independence at the I/O callback boundary, Exit/reopen, and
contribution-driven file dialog metadata. Full native Windows validation
must be performed by the owner after request 3/6 integration. Hosted CI
static validation does not substitute for Qt runtime acceptance.

Integration must stay within the four reserved Enterprise roots and target
`handoff/enterprise-iqa-window`, not PUBLIC `main`. Reconcile concurrent
requests 1–6 before merging; review the same `analysis_window.py`
Open/Save exception handlers (request 5) and hover/readout UI (requests
3 and 6) at the exact integrated head.
