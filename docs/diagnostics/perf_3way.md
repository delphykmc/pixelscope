# Temporary 3-revision GUI performance diagnosis (PUBLIC MAIN only)

This diagnostic branch is not a product change and must not be merged to MAIN.
Goal: identify performance regression between the release immediately before
Issue #77 / PR #80 additive Quick Compare, immediately after that feature, and
the code after PR #187.

## Pinned references

| Stage | SHA | Contract |
| --- | --- | --- |
| V1 | 36f672b6f63943c292ff2ef788f3a1b4ff899031 | PR #80 **before** |
| V2 | 00b7dd77f320adee7a9d681902bb19d86480ea4c | PR #80 **after** |
| V3 | 21c3158c18b01f4f50b322f8e908ec05a85a36a0 | PR #187 merged |

Run comparisons on the same Windows machine, exact same images, warmed disk cache,
window dimensions, display arrangement and Analysis/Histogram panel visibility.
First run without wrappers (\`-NoProbe\`) for perceived responsiveness, then
repeat with the lightweight diagnostic wrappers to identify expensive Python methods.
Do not infer monitor scanout latency from Python call duration.

## Safety / checkout isolation

* PUBLIC checkout: an existing clone of \`delphykmc/pixelscope\`.
* INTERNAL checkout: **never** checked out, modified, committed, or imported
  as a PixelScope source tree. Only its existing virtual-environment Python and
  installed dependencies are shared.
* The internal checkout directory is a **runtime parameter**, not encoded in
  this public diagnostic branch.
* Stage worktrees are detached, SHA-pinned copies under a separate
  \`perf_three_way/worktrees\` directory next to the PUBLIC checkout. The active
  PUBLIC checkout is not switched.
* Logs, per-version QSettings INI files and stage worktrees stay outside the
  tracked repository. The harness redirects normal QSettings into independent
  version-specific INI locations rather than the installed application's usual
  registry settings.
* A strict import check confirms that \`import pixelscope\` resolves to the
  selected PUBLIC SHA even when INTERNAL Python has an editable installation.
  The harness never runs \`pip install\`.
* PRIVATE paths, log files that may contain machine-specific information, and
  test images **must not** be committed or pushed to the PUBLIC repository.

## Setup on Windows PowerShell

First fetch this diagnostic branch into the PUBLIC checkout and create a
separate harness worktree, without switching the original branch:

\`\`\`powershell
$public = 'E:\git\pixelscope_debug\pixelscope'
$harness = 'E:\git\pixelscope_debug\perf_harness'
git -C $public fetch origin diagnostics/perf-3way-regression-20261016
git -C $public worktree add --detach $harness FETCH_HEAD
& "$harness\scripts\diagnostics\perf_3way.ps1" -Action Setup -PublicRepo $public
\`\`\`

When \`perf_harness\` already exists from this branch, reuse it instead
of adding the worktree again. These commands change PUBLIC Git worktree
metadata, not the INTERNAL repository.

Run the three GUI revisions with an INTERNAL virtual environment
(the exact INTERNAL repository path is supplied locally):

\`\`\`powershell
$internal = '<LOCAL_INTERNAL_REPOSITORY_PATH>'
$run = "$harness\scripts\diagnostics\perf_3way.ps1"

& $run -Action Run -Stage V1 -PublicRepo $public -InternalRepo $internal -NoProbe
& $run -Action Run -Stage V2 -PublicRepo $public -InternalRepo $internal -NoProbe
& $run -Action Run -Stage V3 -PublicRepo $public -InternalRepo $internal -NoProbe

# Repeat with timing wrappers (close each GUI before launching the next).
& $run -Action Run -Stage V1 -PublicRepo $public -InternalRepo $internal -TraceThresholdMs 5
& $run -Action Run -Stage V2 -PublicRepo $public -InternalRepo $internal -TraceThresholdMs 5
& $run -Action Run -Stage V3 -PublicRepo $public -InternalRepo $internal -TraceThresholdMs 5
\`\`\`

Python lookup order: \`<internal>/.venv/Scripts/python.exe\`,
\`<internal>/venv/Scripts/python.exe\`, corresponding locations in
\`<internal>/..\`, then \`VIRTUAL_ENV\`.
If different, pass \`-InternalPython 'X:\path\to\venv\Scripts\python.exe'\`.
No environment dependencies are installed or updated.

If an execution-policy restriction blocks local PowerShell scripts,
use a Process-scoped temporary policy or invoke \`powershell.exe -ExecutionPolicy
Bypass -File <script> ...\` according to company policy.

## Manual scenario matrix

Perform each applicable scenario separately for each stage, then reset the
program between cold and warm cases. Use at least five repeats; record median,
slowest observed delay, visible freezes, whether both images repaint together,
and whether the Difference layout disappears.

1. Drop one 4K RGB8 PNG into Files; first image visibly rendered.
2. Drop two 4K RGB8 PNGs together into Files vs onto Image View (different paths).
3. Register a populated folder without selecting any image; check responsiveness.
4. Drag-select two registered files in Files; deselect and reselect rapidly.
5. With A/B selected, explicitly enable Diff (where supported), producing 3 View;
   press + once, then several times. Observe the delay between A/B/Diff tile updates.
6. Select one image from each of two different folders, show Diff, then PageDown
   and PageUp. Record navigation delay, whether layout collapses from 3 to 2,
   and how long until the new Pair/Diff can be viewed.
7. Hold 1-2 files from Explorer above PixelScope Image View without dropping.
   Check cursor/hover freezing and any console method spikes. Repeat over Files.
8. Repeat 4-6 with Histogram/Statistics/Line Profile panel hidden, then visible.

### Feature parity caveats

V1 predates automatic Quick Compare and its 3 View variant controls; test the
corresponding *manual* Difference flow rather than treating missing UX as
performance PASS.  V2 has automatic Diff presentation unlike V3's passive
cache-default-hidden behavior. Keep computation cost and presentation/layout
cost separate in the result table.

## Output interpretation

Logs are written to:
\`<public parent>\perf_three_way\logs\V1-YYYYMMDD-HHMMSS.log\` and
analogous V2/V3 files.  Observational QSettings are under \`settings/V1\`, etc.

* \`[perf-3way] CALL\`: an individual Python method took longer than the
  configured threshold. Calls can include nested method calls.
* \`[perf-3way] SUMMARY\`: count, median, p95, max and summed wall time of
  each instrumented method.
* \`[load-trace]\` / \`[analysis-latency]\`: in-version source tracing, only
  for revisions where those opt-in facilities exist.
* Method times are NOT GUI event-to-photon/monitor scanout times; visibly
  sequential rendering should also be annotated in the manual matrix.
* The probe changes timing slightly; \`-NoProbe\` is the reference for
  subjective comparisons.

Useful candidates: \`MainWindow._selection_changed\`,
\`MainWindow._render_selection\`, \`MainWindow._update_file_states\`,
\`MultiCompareView.set_documents\`, \`ImageViewer._upload_preview\`,
\`ImageViewer._ensure_display_preview\`, \`DifferencePanel.set_documents\`,
\`ComparisonAnalysisPanel.set_documents\`, and RegistrationController.
Note: some listed APIs do not exist on all revisions; absent wrappers are skipped.

## Exit criteria

Identify at least one reproducible V1→V2 or V2→V3 step increase,
separate compute, selection state, viewer binding/paint, Analysis, navigation
state and drag-hover overhead, and only then open implementation PRs.
Do not merge this diagnostic branch, change the INTERNAL repo, or treat
passing unit tests as human interactive performance acceptance.
