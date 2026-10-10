# UX-3B HTML report — offline visual document

**Implementation:** independent Handoff-only slice after merged UX-3B PNG [#163](https://github.com/delphykmc/pixelscope/pull/163). The HTML report is not the versioned IQA result format and does not unlock the #140-gated Open Result / Save Result As actions.

## Workflow

Use AnalysisWindow **File > Export Result > Report (HTML)...**.

- With an active ROI, select **Full image / Active ROI / Both**; without an ROI, use Full.
- Select an existing parent directory. A **new** directory \`iqa-report-<safe-result-id>/\` is created, and existing output folders are never knowingly overwritten.
- Open \`index.html\` in a local browser. All image assets are **fixed-name PNGs in the same folder** and do not require a network connection. Accompanying \`export_info.json\` is a descriptive audit record, not a reloadable schema.

Generated content:

- Independent decoded source A/B PNGs and selected Spatial Map PNG using the exact same source-coordinate mapping, original-resolution crop rectangles, range/gain and invalid-cell alpha as the separately reviewed PNG exporter.
- A comparison table listing **every** adapter-supplied Attribute in source order, group, unit, full-pair availability, complete full-pair comparison value (blank for partial/missing/failed), ROI grid-derived estimate when available, ROI coverage and quality-orientation declaration.
- Scope and map render provenance, valid-cell whole-grid clipping counts and missing image explanation.
- Static responsive/print-friendly CSS. User labels/IDs rendered only as HTML-escaped text. Image names come from fixed internal literals. No dynamic JavaScript, CSS/JS remote dependencies, API calls or external fonts. CSP denies network connections and scripts.

The source pair identity is **A/B**, independent of onscreen pane swap. Signed unoriented metrics must not be interpreted as a quality winner. The report displays source RGB after decoding, **not RAW/bit-exact capture**. GRID-derived ROI values are not producer-verified regional pair scores.

## Failure/publishing behavior

The writer first builds a complete PNG snapshot using the verified PNG exporter within a temporary **same-parent** directory, adds escaped HTML, then publishes the folder in a final rename. On failure or cancellation no partial report is published. The existing PNG export remains unchanged, and an output folder collision returns a user-visible failure. This inherits the PNG writer's current per-raster 16,777,216-source-pixel limit and the non-blocking P2 issues listed on #163 (slow GUI-thread 4K export and cross-platform concurrent empty-directory race); this slice does not modify the performance model.

## Owner acceptance — Windows Python 3.10 / PySide6

\`\`\`powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_html_report.py
& $py -m pytest -q -W error::DeprecationWarning tests/enterprise/iqa/test_analysis_ux3b_html.py tests/enterprise/iqa/test_analysis_ux3b.py tests/enterprise/iqa/test_analysis_ux3a.py
& $py -m ruff check .
& $py -m ruff format --check .
& $py -m mypy src
\`\`\`

Manual: \`& $py -m pixelscope_enterprise.iqa.demo --rgb\`, select ROI / None, switch selected Attribute and Map Gain/Range, export Full/ROI/Both, verify the HTML opens **offline** with correctly cropped A/B/Map PNG and no remote calls. Inspect HTML with a malicious-looking source/Attribute label (rendered as text only). Verify missing A/B/Map placeholders, cancellation, existing folder and normal Qt close/reopen.

Keep PR Draft until exact-head static CI, owner Windows native Qt/UI checks and independent review. Target base: **\`handoff/enterprise-iqa-window\` only**; never PUBLIC \`main\`. PRIVATE SUB transfer/frozen attestation is a separate security gate.
