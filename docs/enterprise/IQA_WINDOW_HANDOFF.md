# Enterprise IQA Window — temporary public-safe handoff

Tracking: [#141](https://github.com/delphykmc/pixelscope/issues/141). Implementation branch: `feat/141-analysis-window-shell` targeting **`handoff/enterprise-iqa-window`, not `main`**.

## Integration provenance

| Field | Value |
|---|---|
| Initial merged MAIN base | `e8959eaa27acc0777542f33a8bf476e3ec6ad28c` (docs PR #142) |
| Public IQA contract revision at base | `IQA_PUBLIC_CONTRACT_REVISION = 1` |
| MAIN host implementation | #139 **in progress**, intentionally not assumed |
| Server output contract | #140 **proposal**, not a finalized file schema |
| Public-safe branch disclosure | All branch files and commits are publicly readable |
| Ownership | Only `src/pixelscope_enterprise/**`, `tests/enterprise/**`, `docs/enterprise/**`, `enterprise/**` |
| Merge prohibition | Do **not** merge any Enterprise path into public `main` |

The initial base is a **development pin**, not a claim that #139 has been approved or
merged. The final MAIN SHA and contract revision must be updated after #139 merges,
before the branch is approved for PRIVATE SUB transfer.

## Implemented preliminary standalone window scope

- One extension-owned, independent non-modal `QMainWindow`, managed as a singleton,
  initially placed on the secondary screen when present. Last geometry is stored under
  a separate company-neutral Enterprise UI settings identity; disconnected-screen
  geometry is rejected in favor of an on-screen fallback.
- Empty opening supported; file **Open/Save As** actions are disabled until a real
  versioned, verified file reader/writer is injected. Result presentation itself
  is strictly user-directed, not triggered by a background job.
- Three source-pixel-coordinate A/B/Map views with shared zoom/pan and Shift+drag ROI.
  Source RGB absence retains official and spatial results. A spatial image uses the
  declared grid geometry and is rendered at grid resolution, not upsampled to 4K.
- Attributes appear in supplied order with unit/group identification, explicit
  official pair comparison and separate **GRID-DERIVED** ROI mean plus valid coverage.
  Missing and failed values are displayed as absent, never silently as numeric zero.
- Attribute/result selection retains ROI, attribute, map range and navigation state
  per result in memory. Fixed symmetric range defaults come **from the adapter**;
  manual range changes affect colors and clamp counts only, not numeric summaries.
- Semantic direction `positive = A better` is not guessed: the adapter must supply
  already quality-oriented values and set `quality_oriented` only where authoritative.
  Neutral metrics explicitly do **not** claim a winner.
- No company-specific code, URLs, paths, payloads, model algorithms or private data.

## Manual standalone preview

In a normal project Python 3.10 environment with editable package and Qt dependencies:

```powershell
$env:PYTHONPATH = "src"
$env:QT_QPA_PLATFORM = "offscreen"  # optional: automated/headless smoke only
python -m pixelscope_enterprise.iqa.demo
```

The demo synthesizes 12 public-safe attributes and an aligned 3840×2160/64 spatial
grid. RGB source files are intentionally absent, making the numeric/map fallback
observable. The synthetic official values do **not** establish scientific
equivalence to a model or server output. For visual inspection on a real screen,
omit `QT_QPA_PLATFORM=offscreen`.

Focused validation (run in the MAIN-compatible Python 3.10 Qt environment):

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/enterprise/test_analysis_model.py tests/enterprise/test_analysis_window.py
```

The implementation environment used to author this handoff did **not** have PySide6
installed and had no network package-install access. The Qt runtime tests are
authored but **not yet executed/verified**. No CI or full-suite success is claimed.

## Explicit follow-up / owner integration gates

1. **#139 MAIN host:** after generic menu/dock/status/window lifecycle changes, pin
   the exact merged MAIN SHA, rebase the temporary handoff branch and exercise the
   already supported `WindowContribution` phases. Introduce no IQA-specific API
   in Base. MainWindow job registry, completion notifications, submit validation,
   async polling and result-view action remain an extension-specific subsequent slice.
2. **#139 MAIN public semantic gap (conditional):** existing public `IqaResult`
   primarily exposes per-variant summaries; it lacks an authoritative first-class
   pairwise *official relative* result. The downstream `AttributeDisplay` boundary
   temporarily decouples the UI. Decide only after sanitized #140 schema/fixture
   shows if a small additive public pair-comparison contract is required. Do not
   infer official scores from grid means or rounded per-image dB.
3. **#140 server contract:** provide normalized, validated per-attribute signed
   grids, official comparison semantics, masks, geometries and a portable immutable
   artifact. H2 reader/writer must validate versions, hashes, sizes, compression,
   array dtypes, path confinement and reject pickle. File handlers remain disabled
   until real round-trip tests exist.
4. **Follow-on window slices:** a real grouped bipolar chart, cursor crosshair,
   finer drag ROI feedback, sliding-window hotspots, image/CSV/HTML exports, persisted
   analysis state in Save As, DPI/4K performance measurements, multiple monitor
   lifecycle and stale-worker verification. Current attribute table is a functional
   interim inspector, not the final 10–12 metric chart.
5. **Transfer:** after review and validation, import only allowlisted SUB-owned
   paths from the pinned handoff SHA into PRIVATE SUB. Verify commit/path manifest and
   tests there. Do not cherry-pick or merge the public Enterprise branch into MAIN;
   remove the temporary branch only **after** proven transfer. Keep private adapters
   and config exclusively in PRIVATE SUB.

## Rebase procedure when #139 completes

```powershell
git fetch origin main
git switch handoff/enterprise-iqa-window
# Rebase only after identifying the reviewed #139 merged MAIN SHA.
git rebase --onto <APPROVED_MAIN_SHA> e8959eaa27acc0777542f33a8bf476e3ec6ad28c
git switch feat/141-analysis-window-shell
git rebase --onto handoff/enterprise-iqa-window e8959eaa27acc0777542f33a8bf476e3ec6ad28c
```

Review both branches' HEAD, diff allowlist and tests after rebase. The first
command normally only moves a zero-change handoff baseline forward. Avoid
force-pushing over another agent's work: check the remote head and use a lease.
