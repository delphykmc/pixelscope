# IQA one-pair Analysis Window: temporary handoff implementation plan

Status: **specification only**; implementation is reserved for a separate session. Tracking: [#141](https://github.com/delphykmc/pixelscope/issues/141). Precursor [#136](https://github.com/delphykmc/pixelscope/issues/136); MAIN host scope [#139](https://github.com/delphykmc/pixelscope/issues/139); server result contract [#140](https://github.com/delphykmc/pixelscope/issues/140); UX discovery [#137](https://github.com/delphykmc/pixelscope/issues/137).

## Branch ownership and preconditions

- PUBLIC MAIN main contains only generic Core/Host, public IQA ports, and MAIN-owned Reference Lite. SUB-owned Enterprise paths **never merge into PUBLIC main**.
- Implement the actual IQA Window in the *temporary PUBLIC branch* `handoff/enterprise-iqa-window` created from a **verified, merged MAIN commit SHA** after required generic MainWindow hosting changes. The precise SHA must be recorded in the Handoff manifest when work begins; do **not** assume this spec's docs branch HEAD is an integration baseline.
- Use only `src/pixelscope_enterprise/**`, `tests/enterprise/**`, `docs/enterprise/**`, `enterprise/**`. Enterprise implementation must not import `pixelscope_iqa_reference` helpers; both are independent consumers of MAIN host and public IQA contracts.
- Reuse or continue #136 bootstrap where compatible; do not create duplicate ownership or production code copies. #136 is a replaceable skeleton with public-safe fake provider, not a mandate to preserve its early Dock layout.
- Every line of the temporary branch is publicly visible during its existence and can survive deletion in forks/caches. **Only company-neutral code, synthetic data and fixtures**; no corporate roots, auth, networks, proprietary algorithms or real data.

## Operator journey and UI structure

### Host MainWindow

1. Select exactly two original image paths A and B, capture frozen order and immutable source identity at submit. For initial product assume same-resolution RGB, pixel-aligned. Preserve slot cardinality; if inputs invalid, explain and do not silently substitute.
2. `Run IQA` is an **Extension-contributed** action/toolbar or compact jobs UI. The underlying Job registry and execution controller are Extension-owned. Supports multiple queued/running jobs independently of currently viewed images.
3. Status visible in MainWindow: QUEUED, RUNNING, COMPLETED, FAILED, optional CANCELLED, with sanitized messages, optional progress and explicit cancel availability. The user can keep working; completion is **not** an automatic navigation.
4. On completed result being materialized, enable a user-selected `View Result` action. Completed compute vs artifact ready-to-open must be distinguishable. A new completion does not auto-replace an already opened result.
5. Independent `Open IQA Analysis` action creates/shows the single non-modal Analysis Window even with no result.

### IQA Analysis Window — Extension-owned, 1 instance

```text
File: Open Result... | Save Result As... | Export...
Result selector: (recent/current)
Main area: Image A | Image B | Relative Spatial Map
Right fixed, resizable Inspector:
   Attribute Overview (preserved supplied order, grouped dB vs signed delta)
   Global official comparison / selected ROI derived or official values
   Hotspot Top 3–5 and ROI controls (default 512x512 original px)
   Map scale/legend/clipping and export actions
```

- Initially opens empty, `Open Result...` accepts saved local package; no Job required. Source missing -> A/B placeholder, but valid attribute/map/statistics render.
- Maps align to source-pixel geometry; initial 4K source, nominal grid block about 64x64 original px, actual metadata authoritative. Three views have linked cursor/ROI/zoom/pan; ROI persists when Attribute changes. Native RGB not scaled for model because the UI is on an FHD screen.
- Relative values are quality-oriented positive A better / negative B better where metric metadata supports that mapping. Units and quality semantics are explicit, no fabricated winner for neutral metric.
- Chart presents all ~10–12 attributes, preserving source-defined order and grouping comparable units under a shared scale (dB majority, signed delta separate). Do not imply dB and signed delta magnitudes are directly rank-comparable; no automatic global rank from unrelated scales.
- Map color ranges use fixed zero-centered bipolar defaults per truly compatible unit/group, Attribute override where needed, user-adjustable bounds, explicit clamp count/percentage/legend. **Never use robust percentile or auto contrast** as default; clipped display does not change ROI/hotspot raw inputs.
- Hotspots: sliding-window search using user-configured original-pixel rectangle default 512x512, Top 3–5, valid-coverage guard and overlap suppression; stage algorithm sophistication separately. ROI local grid-derived summary must be clearly distinguished from **official** full-pair comparison. Official ROI only if server produces or client reconstructs exact metric via documented sufficient stats.
- A/B source files may fail to resolve; numerical and spatial exploration remains usable.
- Result selector keeps UI state per Result ID (attribute, ROI, viewport, range, hotspot), reloads state on switching. In-memory-only results lose this on exit; persistent saved packages preserve `analysis_state`.
- Window first opens on available secondary monitor if possible; afterward restores last user screen/geometry safely, constrained to visible screen with mixed-DPI and unplug behavior. It must not manipulate MainWindow image selection, analysis panes, ROI, zoom or dock state.

### Save As / exports

- `Save Result As...`: losslessly re-openable portable result, including manifest, official summary, numeric grid/mask/artifacts, source identity, separate user analysis state. Original RGB not required. Different destination/display label does **not** rewrite scientific origin/identity; record separate document label if desired.
- `Export Images...`: A/B matched crops, selected Map/overlay and labels. Missing A/B handled gracefully.
- `Export CSV...`: official global and clearly labeled Grid-derived ROI measurements, units, validity, source identity.
- `Export HTML...`: standalone client-generated shareable report with text+images+metrics+ROI/context; integration with a possible server report is later work. Do not mix with Save As.

## Implementation work packages

| Slice | Primary change | Required evidence |
|---|---|---|
| H0 | exact MAIN baseline + #136 bootstrap audit; SUB-only branch layout; composition root and fakes | scope/path purity, Core untouched, synthetic conformance |
| H1 | MainWindow Run/status/View Result + empty singleton non-modal window + monitors | nonblocking UI, accurate job state, repeated child creation/shutdown |
| H2 | official pairwise result adapter, synthetic JSON/NPZ parser, local open/save and corruption guard | round-trip & source-missing, versions, array bounds/pickle disabled |
| H3 | A/B + Map Views, Inspector, fixed ranges, linked ROI/cursor/zoom | pixel coordinate contract, 4K performance, display clipping and direction |
| H4 | result state switching, hotspot, CSV/image/HTML exports, errors/partial states | deterministic UX and offline acceptance |
| H5 | packaging, native Qt lifecycle, exact-SHA provenance, transfer checklist | public-safe review and SUB-side verified import |

If P0 server schema is not yet settled, H1 may proceed with public synthetic types; H2 must use a versioned adapter/interface so the private implementation can replace files without rewriting UI.

## Integration and transfer procedure

1. MAIN generic host changes are reviewed and **merged**. Record `MAIN_SHA`, public `IQA_PUBLIC_CONTRACT_REVISION` and reason for any host changes.
2. In an external implementation session, create the **temporary** handoff branch from that SHA and constrain all commits to SUB-owned paths. PRs may target the temporary branch (or be reviewed by diff/commit) but **never PUBLIC main**.
3. For each slice, validate locally against synthetic fixtures and appropriate CI. Do not depend on private server or credentials.
4. Before exposing deliverable, conduct public disclosure/security review; produce an explicit approved HANDOFF SHA and file manifest (paths, hashes, tests).
5. In PRIVATE SUB with a MAIN-derived Git history, fetch approved MAIN SHA and integrate it with private SUB changes using the existing upstream workflow. Then copy only reserved paths **from the pinned handoff commit** into an internal branch and commit them:
   ```powershell
   git fetch upstream main handoff/enterprise-iqa-window
   # after choosing approved exact MAIN SHA and preparing a private integration branch
   git restore --source=<APPROVED_HANDOFF_SHA> -- src/pixelscope_enterprise tests/enterprise docs/enterprise enterprise
   git add src/pixelscope_enterprise tests/enterprise docs/enterprise enterprise
   git commit -m "Import approved public-safe IQA handoff"
   ```
   This is an example for a shared-history, full-tree SUB checkout; teams with a different repository model should adapt. The `git restore` command does **not** import handoff branch commits as ancestors; preserve the provenance SHA/manifest explicitly. Compare file hashes and conformance tests in SUB.
6. Add real shared-storage, network, model and authentication adapters only inside PRIVATE SUB. Verify conformance and installation. After owner confirms a verified SUB import, delete temporary public handoff branch. Deletion is cleanup, not privacy rollback.
7. Future generic bugs/host needs return to MAIN as **company-neutral** requirements, upstream implementation/tests first, then SUB fetch/merge exact approved MAIN SHA. Do not retain permanent patches to MAIN-owned files in SUB.

## Mandatory test matrix

- MAIN Core-only and explicit Reference remain buildable; no unintended imports.
- User can initiate Job A/B, switch MainWindow to unrelated images and still see the correct Job ID/Pair/Completion; no automatic display swap.
- One Analysis Window, opens empty, no Job required; locally saved result opens offline, Save As round-trips numeric arrays and user state.
- Two or more results keep distinct Attribute, ROI, zoom and ranges; late callbacks from previous Result/window cannot alter the active view.
- Source Missing, failed, partial, invalid, zero-valued and out-of-range Map cells are distinguished; correct A/B sign and metric orientation.
- Slider/range change affects color only; no change to actual metric, ROI/hotspot.
- Exact source/grid transform, last row/column partial cells, sync ROI and native 4K side-by-side coordinate checks.
- FHD/UHD, multi-monitor/mixed DPI, window positioning, unplug/reconnect; all three views legible with resizable right inspector.
- Repeated open/close under normal GC with explicit pyqtgraph `ImageViewer.shutdown()`, cancelled worker callbacks, no suppressive sleeps or shutdown hacks (#81).
- Synthetic adapter rejects unsafe/absolute path traversal, oversize/dtype-mismatched NPZ, missing checksum/READY, unsupported schemas.
- Internal server/staging/auth/package smoke is SUB-only; do not falsely claim tested by public synthetic runs.

## Exit criteria

- Approved, reviewed PUBLIC-safe handoff commit; no Enterprise paths ever merged into PUBLIC main.
- Documented explicit exception for any contract/interface gap, handled via approved MAIN PR.
- Reproducible synthetic UX demo and lifecycle/conformance evidence.
- Verified imported files and internal smoke in PRIVATE SUB; cleanup of temporary public branch only after verification.
