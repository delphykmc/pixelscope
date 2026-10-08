# IQA MAIN host ownership and Reference Lite plan (proposed)

Status: specification for review, **no implementation authorized by this document**. Tracking: [#139](https://github.com/delphykmc/pixelscope/issues/139). Related: [#121](https://github.com/delphykmc/pixelscope/issues/121), [#136](https://github.com/delphykmc/pixelscope/issues/136), [#137](https://github.com/delphykmc/pixelscope/issues/137), [#140](https://github.com/delphykmc/pixelscope/issues/140), [#141](https://github.com/delphykmc/pixelscope/issues/141).

## Decision and authority

The original #121 separation remains binding: PUBLIC MAIN owns Core/generic host, public IQA data/protocol boundary, and optional public Reference; PRIVATE SUB owns final IQA product, compute/storage/auth adapters, and internal packaging. The later UX discovery **changes the Reference's intended depth**, not these ownership boundaries. In contrast to the earlier #137 candidate of a full public IQA UX prototype, the **approved proposal for implementation review** is a compact Reference Lite / integration canary. An agreed detailed UX can be developed with synthetic data directly in an unmerged PUBLIC handoff branch under SUB-owned paths, then explicitly imported into PRIVATE SUB.

This decision should be adopted into the permanent handoff/Reference docs when approved; the current production code remains untouched.

### Composition and scope

| Surface | PUBLIC MAIN Core | MAIN Reference Lite | TEMP PUBLIC handoff / PRIVATE SUB |
|---|---|---|---|
| Default PixelScope / viewer / files / RAW / YUV | Own | Consume | Consume |
| Generic menu/dock/settings contribution hooks | Own | Exercise | Consume |
| Narrow generic selection and child-window lifecycle seam | Own only if proved necessary | Exercise | Consume |
| Qt-free public job/result boundary / fixture / conformance | Own | Exercise with mock | Implement public ports |
| MainWindow Run IQA + jobs widget | No IQA-specific controls in Base | Small mock contributed UI | Real contributed UI |
| Concurrent queued/running/completed job registry | No ownership | Deterministic mock | Real extension controller |
| Empty independent non-modal IQA Window | Generic ability only | Minimal canary window | Production analysis window |
| A/B/Map, inspector, ROI, hotspot, report | No | No | Own |
| Local Open/Save As, JSON/NPZ adapter | No | Not required | Own |
| Shared data/compute/auth/SSO and retention | No | No | PRIVATE SUB only |
| Final IQA UI and enterprise packaging | No | No | Own |

MAIN default packaging stays Core-only. MAIN public reference remains explicitly opt-in and company-neutral. Reference-private helpers are never a SUB dependency.

## UX to preserve across implementations

- Job invocation belongs to a contributed MainWindow command; status stays visible there while image selection and ordinary analysis continue. MainWindow does **not** become owner of IQA job semantics.
- Execution/job registry, published results and IQA Analysis Window have **independent lifetimes**. A completed job is distinct from a locally ready-to-open result; no automatic result switch.
- Extension owns one non-modal secondary `QMainWindow`. It can open empty and load existing artifacts without job history; in production it supports Save Result As and analysis state.
- Results are one pair of pixel-aligned, same-resolution RGB images. Production analysis view is independent from the MainWindow's selection, zoom, ROI and dock state; 2nd monitor placement is SUB UI policy.
- Production result UX has three coordinated A/B/Map views and a fixed resizable inspector. These are NOT Base or Reference requirements.
- MainWindow should not acquire IQA-specific event bus, data model, widget slots or persistence. If a generic UI contribution is unavailable, demonstrate the deficiency with a public canary test then add only that smallest seam.

## MAIN implementation work breakdown — separate implementation session

### M0. Prove existing host sufficient

Existing `WindowContribution.prepare/install_dock/install_actions/shutdown`, optional `install_runtime`, `SettingsWindowContribution`, and `WindowHostAccess.current_comparison_source_paths()` already allow action contribution and slot-preserving paths.

- Prototype a small `Run IQA` action and jobs overview using existing contribution-owned UI. Require exactly two native source paths and capture immutable pair identity at submission; no silent filtering of `None` slots.
- Exercise queued/running/completed/failed and explicit View Result on a deterministic mock. Mock job progress must not rely on blocking the GUI thread.
- Compare Toolbar vs StatusBar vs compact Dock in a real MainWindow at FHD; choose the smallest adequate location **before** adding a new host hook. IQA widgets must remain extension-owned.
- Test multiple Job IDs vs one result-view window; one GUI window does not constrain number of server jobs.

### M1. Conditional generic host addition

If M0 demonstrates insufficiency, add a small product-agnostic contribution host, e.g. `register_contributed_toolbar` or `register_contributed_status_widget` plus shutdown/geometry handling. API naming and lifecycle contract are not frozen here; write a generic conformance test first. Do not invent dynamic plugin discovery, hot-loading or broad event bus.

A contributed standalone secondary window may be owned and cleaned by the extension's idempotent `shutdown()` with the existing lifecycle. Add a generic host lifecycle registration only if that cannot be proved robust.

### M2. Reference Lite cutoff

Keep public `pixelscope-reference` launcher/build, deterministic `FixtureIqaProvider`, public port conformance, action/dock/status canary, mock result opening, and explicit independent child-window open/close. Existing Reference/Scene combobox and first-attribute-only text presentation are disposable and should not be cosmetically rebuilt as a substitute for real UX.

Mock Result's `open_result()` is *not* proof of filesystem persistence. Do not claim genuine saved file Open/Save As based on fixture-only materialization. UI named `Open Result...` must perform real file selection or clearly state synthetic demo semantics; production file reader stays SUB-owned.

Do **not** create a parallel production A/B/Map implementation, NPZ serializer, ROI inspector or HTML report within MAIN Reference.

### M3. Public IQA semantic additions — conditional

Keep `IqaExecutionPort`, `IqaResultAccessPort`, normalized `IqaResult` and lazy spatial. Current `IqaResult` exposes per-variant dataset/scene summaries but does not directly expose a first-class official single-pair relative comparison summary. The public `iqa_domain.Comparison` contains historical official comparison modes; evaluate an **additive, normalized pair-comparison view** only when the server contract and UI adapter have a concrete need, with synthetic conformance tests. Preserve compatibility/revision policy.

Generic schema must not contain real storage paths, server endpoints, tokens, proprietary algorithm detail or company-specific config. Physical JSON/NPZ/manifest adapters and portable Save As are downstream-owned.

### M4. Packaging, documentation and tests

- Core import graph excludes reference/enterprise; no dynamically discovered add-on requirement.
- Reference opt-in runner can exercise Mock jobs/status, child-window lifecycle and shutdown.
- No Qt object leakage, stale callback touching deleted widgets, new unbounded pools, GC disable, hidden sleeps, forced timeouts or exception swallowing (Issue #81).
- Source pair selection/Job ID identity, public port overlapping calls and ambiguous-submit are covered.
- Exact merged MAIN SHA and contract revision are recorded for handoff.

## Acceptance / implementation gate

1. M0 measured/observed first: **no preemptive Base UI modification**.
2. Any Base addition belongs to generic host code and generic tests, not IQA product widget ownership.
3. Original #121 two-peer dependency direction is preserved; no PUBLIC MAIN path under SUB-reserved namespaces.
4. Replacement Reference is narrow and publicly runnable; previous Reference features may be retired in a separate reviewed PR with tests/docs updated.
5. Handoff Window implementation waits for an exact *merged* MAIN baseline; any missing generic contract returns upstream as a new MAIN PR.

## Non-goals

No real server inference, authentication, shared-storage routing, enterprise secrets, full IQA Window, hotspot, image report, and no assumptions about proprietary metric formulas. This is an ownership/scope specification, not a runtime change.
