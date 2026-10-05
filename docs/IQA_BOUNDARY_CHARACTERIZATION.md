# Current IQA boundary characterization

Status: Issue #121 Slice 1 characterization contract.
Baseline: `main@cb48f64059c19b8bbcccc248d06c6519ea650bb0` (merged Slice 0 / PR #122).

This document records the **current physical IQA integration boundary** that later
Issue #121 slices must preserve while introducing the staged Base + IQA Client +
Enterprise ownership model from `IQA_OWNERSHIP.md`.

Slice 1 is characterization only. It does not rename or relocate production modules,
change runtime composition, alter settings behavior, change Qt ownership, or weaken
existing IQA/UI/lifecycle tests.

## Reading rule: physical location is not target ownership

The current repository predates the staged ownership boundary. Some Base files import
IQA-specific modules directly, and some Enterprise-target configuration is currently
stored by the MAIN application settings repository. Those facts are **inventory**, not
a decision that those dependencies belong in Base or MAIN permanently.

Use these two views together:

- `IQA_OWNERSHIP.md` answers **which layer should own the contract**.
- this document answers **where the current implementation is coupled today and what
  behavior must remain compatible while the seam is introduced**.

The target rule for new work remains:

```text
Enterprise IQA -> IQA Client -> PixelScope Base
```

The arrow means depends on.

## Current physical boundary

### `src/pixelscope/app/main_window.py`

`MainWindow` currently has direct compile-time knowledge of the IQA Client UI. It
imports `IqaWorkspaceController` and `IqaWorkspaceWidget` from
`pixelscope.ui.iqa_workspace` and performs all of the following itself:

- accepts an optional `iqa_result_pool` constructor argument;
- constructs `self.iqa_workspace = IqaWorkspaceWidget()`;
- constructs `self.iqa_controller = IqaWorkspaceController(...)`;
- constructs the `QDockWidget("IQA", ...)` shell and sets the IQA workspace as its
  widget;
- contributes **File > Open IQA Result...** and **View > Show IQA Workspace** actions;
- implements `open_iqa_result()`, including directory selection, showing/raising the
  dock, and calling `self.iqa_controller.open_result(Path(root))`;
- calls `self.iqa_controller.shutdown()` during `closeEvent`;
- includes the IQA dock in floating-dock title/lifecycle handling.

This is the clearest current **Base -> concrete IQA Client coupling**. Slice 1 freezes
it as observed behavior; it does not legitimize that dependency as the Stage 2 host
API.

### `src/pixelscope/app/application.py`

The production composition root currently imports and installs concrete Remote IQA
modules directly. The IQA-specific imports cover:

- `ReusableIqaClientPool` transport pooling;
- `install_remote_iqa` composition/lifetime installation;
- Remote IQA transport lifecycle, diagnostics, preview lifecycle, submission
  lifecycle, result mapping, result retry, setup presentation, request debug, and
  replay debug;
- P5-D scene inspection and its lifecycle adapter;
- P5-E historical result installation and lifecycle adapter;
- the dedicated `remote_iqa_thread_pool()` result/file pool.

This concrete composition is transitional. Later Issue #121 slices may put a seam in
front of it, but must preserve the behavior described below before ownership is moved.

### `src/pixelscope/ui/composition_lifetime.py`

The lifetime composition layer currently bridges the existing Base-owned window and
Remote IQA implementation:

- `install_remote_iqa_settings_dialog(window)` layers the Remote IQA settings page onto
  the common settings shell;
- the existing `window.iqa_workspace` is wrapped by `RemoteIqaWorkspace`, which adds
  Setup and Jobs around the existing Results UI;
- `NonOwningRemoteIqaController` changes the controller's `window` edge to a weak
  reference;
- the controller receives `window.iqa_controller` as its result controller;
- a window-owned `_NonOwningRemoteIqaCloseFilter` weakly references the Remote IQA
  controller and calls `shutdown()` on window close;
- the composed objects are retained as `window.remote_iqa_workspace`,
  `window.remote_iqa_controller`, and `window._remote_iqa_close_filter`.

The weak/non-owning edges are lifetime hardening, not optional architecture cleanup.
Issue #81 remains authoritative for changes to these QObject/QWidget relationships.

### `src/pixelscope/app/settings.py`

The common settings repository currently imports `RemoteIqaSettings` and owns its
persistence in application settings schema version 6. The current persisted keys are:

- `settings/remote_iqa/server_base_url`;
- `settings/remote_iqa/storage_roots_json`;
- `settings/remote_iqa/staging_root_id`.

`ApplicationSettings.remote_iqa` is therefore physically stored in the Base-adjacent
settings aggregate today, and the keys participate in the common owned/reset/migration
path. This is transitional coupling; Issue #121 Slice 7, not Slice 1, owns settings
cleanup.

### `src/pixelscope/ui/iqa_remote_settings.py`

The Remote IQA settings extension subclasses the common `SettingsDialog`, adds a
**Remote IQA** page, and replaces the window's settings-dialog factory through a
`WeakOwnerHook`. The page exposes:

- server base URL;
- logical shared-storage root IDs mapped to machine-local absolute/UNC client paths;
- optional staging root selection.

Saving still delegates to the common `SettingsRepository`, then notifies the current
Remote IQA controller through `settings_changed()` when one is installed.

## Production construction and install order compatibility contract

Later slices must preserve the observable ordering unless an explicit lifecycle change
is separately justified and validated.

### Application startup

`main()` currently performs this sequence:

1. create the QApplication and load settings;
2. initialize the local analysis thread pool;
3. initialize the application-owned Remote IQA result/file pool;
4. construct `MainWindow(..., iqa_result_pool=result_pool)`;
5. compose the remaining presentation/features around that window;
6. apply icon, show the window, and enter the application event loop.

Initializing the local analysis pool before the Remote IQA result/file pool preserves
the existing `aboutToQuit` clear/wait registration order. The unit composition contract
asserts local analysis clear/wait before Remote IQA result/file clear/wait.

### Remote IQA composition

`_compose_remote_iqa(...)` currently installs the chain in this exact order:

1. `install_remote_iqa(...)` — P5-C Setup/Jobs shell, controller, settings hook;
2. retain the reusable HTTP transport pool on the window;
3. install transport lifetime;
4. install diagnostics;
5. install preview lifecycle;
6. install submission lifecycle;
7. install result mapping;
8. install result retry;
9. polish Setup presentation;
10. install request debug;
11. install replay debug;
12. install P5-D native scene inspection with the shared result/file pool;
13. install P5-D inspection lifecycle;
14. install P5-E historical results with the same result/file pool;
15. install P5-E historical-results lifecycle.

`tests/unit/test_application_composition.py` is an executable canary for this order and
for the shared result-pool identity.

## Current worker and shutdown compatibility contract

Ownership separation must not silently change any of these lifetime properties.

### Pool domains

The current runtime uses distinct resource domains:

- **local analysis pool** — Statistics/Difference/local background analysis;
- **Remote IQA result/file pool** — one application-owned fixed max-two pool used by
  P5-B result loading and forwarded to P5-D inspection and P5-E historical result work;
- **P5-C job-operation pool** — a separate controller-owned max-two `QThreadPool` for
  create/status/cancel/result-resolution operations;
- **HTTP transport pool** — reusable physical clients are leased lazily to executing
  work; queued work does not own a physical HTTP client.

A future provider seam must not collapse these pools merely to make the API look
simpler.

### Client-side stale/cancel behavior

`IqaWorkspaceController` and the Remote IQA controller both use active/generation
state and worker cancellation to suppress stale completion. The Remote IQA controller
shutdown path:

- becomes inactive and advances generation;
- stops polling;
- cancels and clears tracked workers;
- clears polling/result-fetch/result-resolution tracking;
- clears its P5-C job-operation pool;
- deliberately does **not** issue remote job cancellation because server jobs are
  durable across PixelScope close.

The provider/result seam introduced later must preserve these semantics. Provider
implementation cleanup must not move Qt generation/stale-result responsibility into an
Enterprise adapter unless a later lifecycle-specific decision explicitly replaces the
current contract.

### Window close

Current close handling has more than one intentional layer:

- the MainWindow shuts down its P5-B IQA result controller;
- the non-owning Remote IQA close filter shuts down the P5-C Remote IQA controller;
- application-owned background/result pools have their existing QApplication
  `aboutToQuit` clear/wait registration;
- transport/inspection/history lifecycle adapters retain their existing explicit
  teardown responsibilities.

Issue #121 boundary work must preserve idempotence and the Issue #81 non-owning
lifetime constraints rather than replacing them with broad QObject ownership changes.

## Settings ownership classification

The table separates **current storage location** from **target semantic owner**.

| Setting/capability | Current physical location | Target owner | Slice 1 interpretation |
|---|---|---|---|
| settings repository/schema/migration/reset mechanism | `app/settings.py` | Base | Generic application infrastructure remains Base-owned. |
| common Settings dialog shell | `ui/settings_dialog.py` | Base | Generic category/page host remains Base-owned. |
| generic dock/workspace persistence mechanism | common UI host | Base | Base owns the mechanism, not feature-specific IQA meaning. |
| `ui/iqa_floating_geometry` | IQA workspace presentation | IQA Client | IQA dock presentation preference; may use Base persistence services. |
| Remote IQA server base URL | `ApplicationSettings.remote_iqa` | Enterprise | Real transport endpoint is Enterprise configuration even though MAIN stores it today. |
| storage-root ID -> local/UNC client-path mapping | `ApplicationSettings.remote_iqa` | Enterprise | Real internal storage/path convention belongs behind the Enterprise adapter. |
| staging root ID | `ApplicationSettings.remote_iqa` | Enterprise | Submission/storage deployment configuration, not a Base setting. |

No setting is moved in Slice 1. Slice 7 may change physical storage after the
provider/handoff path has been proven.

## Existing IQA validation inventory

The repository already has broad IQA coverage. Slice 1 does not rename, relocate, or
rewrite these tests.

### Public result/domain and synthetic semantic tests

Representative unit coverage includes:

- `tests/unit/test_iqa_explorer.py`;
- `tests/unit/test_iqa_current_pair_contract.py`;
- `tests/unit/test_remote_iqa_v1.py`;
- `tests/unit/test_remote_iqa_v2.py`;
- `tests/unit/test_remote_iqa_v2_limits.py`;
- `tests/unit/test_remote_iqa_v2_review_regressions.py`;
- `tests/unit/test_p5c_partial_v2.py`;
- `tests/unit/test_p5d_scene_inspection.py`;
- `tests/unit/test_p5d_source_locator_identity.py`;
- `tests/unit/test_p5e_iqa_history.py`.

These exercise local/synthetic data shapes, schemas, explorer semantics, partial
states, source identity, and history behavior without a confidential backend.

### Transport/storage/provider-adjacent deterministic tests

Repository-side transport and submission coverage includes:

- `tests/unit/test_p5c_submission.py`;
- `tests/unit/test_p5c_submission_cancellation.py`;
- `tests/unit/test_p5c_storage_hardening.py`;
- `tests/unit/test_p5c_request_debug.py`;
- `tests/unit/test_p5c_debug_replay.py`;
- `tests/unit/test_p5c_localhost_http.py`;
- `tests/unit/test_p5f_transport_pool.py`;
- `tests/unit/test_p5f_compatibility_probe.py`;
- `tests/unit/test_p5f_diagnostics.py`;
- `tests/unit/test_remote_iqa_diagnostics.py`;
- `tests/unit/test_remote_iqa_storage_diagnostics.py`;
- `tests/unit/test_remote_iqa_transport_policy.py`;
- `tests/unit/test_p5g_iqa_preflight.py`.

`test_p5c_localhost_http.py` uses real loopback HTTP against a repository-owned fake
server; it is transport-realistic but still synthetic and Enterprise-free.
`test_p5g_iqa_preflight.py` uses a fake `IqaJobClient` to verify the preflight tool's
contract. Neither is evidence that a live enterprise endpoint was exercised.

### Qt/UI/lifecycle tests

Current IQA UI and lifecycle coverage includes:

- `tests/ui/test_beta_pass2_iqa_stress.py`;
- `tests/ui/test_p5b_iqa_workspace.py`;
- `tests/ui/test_p5c_authority_closeout.py`;
- `tests/ui/test_p5c_debug_replay_ui.py`;
- `tests/ui/test_p5c_remote_iqa.py`;
- `tests/ui/test_p5c_result_mapping.py`;
- `tests/ui/test_p5c_result_retry.py`;
- `tests/ui/test_p5c_setup_presentation.py`;
- `tests/ui/test_p5c_submission_lifecycle.py`;
- `tests/ui/test_p5d_alias_spatial_binding.py`;
- `tests/ui/test_p5d_review_closeout.py`;
- `tests/ui/test_p5d_stale_inspection.py`;
- `tests/ui/test_p5d_viewer_linked_inspection.py`;
- `tests/ui/test_p5e_file_menu_order.py`;
- `tests/ui/test_p5e_historical_results.py`;
- `tests/ui/test_p5e_review_regressions.py`;
- `tests/ui/test_p5f_worker_isolation.py`.

Cross-cutting composition/lifetime canaries include
`tests/unit/test_application_composition.py`,
`tests/unit/test_qt_lifecycle_architecture.py`, and
`tests/ui/test_issue81_qt_lifecycle.py`.

### Live integration boundary

There is currently **no IQA test under `tests/integration/` that requires the real
Enterprise backend, GPU model service, SMB topology, credentials, or private data**.
The deferred external P5-G plan remains the authority for environment-dependent
GPU/SMB/live-service validation. Repository PASS therefore means public/synthetic,
mocked, localhost, and owner-local UI contracts passed; it must not be reported as a
live Enterprise integration PASS.

## Current user flows crossing the boundary

Four flows define the minimum behavior a later seam must support.

### 1. Open an existing IQA result

Current path:

```text
File > Open IQA Result...
  -> MainWindow directory selection
  -> IqaWorkspaceController.open_result(Path)
  -> canonical result reader / explorer model
  -> IQA Results presentation
```

The future Client contract must preserve the ability to open a result source without
requiring the Client to understand a proprietary Enterprise payload.

### 2. Submit and track IQA work

Current Remote IQA UI supports current-pair and folder-pair submission, job progress,
cancellation, result publication/resolution, and opening the resulting IQA result.
Today the implementation exposes server URL, storage-root mapping, HTTP client types,
and portable-storage request details inside MAIN. Those are implementation details to
be pushed behind the Enterprise adapter, not requirements for the public provider API.

### 3. Inspect result-linked source images

P5-D links scene/result source identity back into native PixelScope inspection. The
public Client contract therefore needs a company-neutral source identity/location
shape sufficient for the Client to ask Base host services to inspect a source. It must
not require confidential storage topology or an Enterprise physical path convention.

### 4. Open historical results

P5-E opens previously published results and presents provenance/history through the
same IQA Results experience. Provider/result-source design must therefore allow a
stable public result identity and result metadata independent of the live submission
transport.

## Minimum public Client-owned surface for Slice 2

Slice 1 intentionally records requirements rather than freezing Python class names or
method signatures. Slice 2 should introduce the smallest seam that satisfies the
following current behavior.

### Public result/domain data required by the Client

The Client needs company-neutral semantics for:

- stable result identity and display/provenance metadata;
- dataset/result label;
- variant identities/labels and reference relationship;
- attribute/metric descriptors, including value kind and presentation-relevant
  direction/range semantics;
- scene identities/order;
- scalar/per-scene values;
- optional spatial-grid values and the ability to defer expensive grid/reference
  preparation;
- missing/partial/failure state and public diagnostics needed for UI presentation;
- public source locators sufficient for native scene inspection/history without
  exposing Enterprise storage topology.

The public result contract should describe what the Client presents. It should not be
an exported copy of a proprietary server response.

### Provider/result-source capabilities required by the Client

The current UI implies two logical responsibilities, which Slice 2 may represent with
one small protocol or two focused ports:

1. **IQA execution/provider capability**
   - accept a public IQA request derived from the Client's current-pair/folder-pair
     intent;
   - expose stable public job identity/state/progress/message semantics;
   - support cancellation where the backend allows it;
   - produce a public result source/reference when work is published.
2. **IQA result-source capability**
   - open/load a public result independently of a live submission;
   - provide the public result/domain data needed by Results, history, and inspection;
   - permit deferred/lazy acquisition of heavy spatial data when needed by the current
     UI rather than forcing eager grid preload.

The precise split is deferred to Slice 2. Do not introduce a generalized plugin
framework solely to model these two responsibilities.

### Explicitly outside the public Client port

The following current implementation details are **not** requirements of
`IqaProvider` / the result-source contract:

- server base URL;
- HTTP client classes, connection pooling, timeouts, or retry transport details;
- storage-root IDs mapped to internal/local/UNC paths;
- staging-root selection and enterprise path publication rules;
- credentials/auth/security integration;
- proprietary request/response schema;
- model/server implementation;
- QObject/QWidget/QThreadPool ownership;
- MainWindow menu/dock construction;
- dynamic plugin discovery, entry points, hot loading, or version negotiation.

Enterprise adapters may use those details internally. The Client must consume only the
public capability/result semantics it needs.

## Client/Base lifecycle division for the future seam

The provider contract should remain Qt-free where practical. The existing Client
controller should continue to own UI-facing async/lifecycle policy such as:

- generation/stale-result suppression;
- TaskWorker/QThreadPool scheduling chosen by the Client composition;
- presentation loading/error/partial states;
- cancellation of Client-owned pending work on close.

Base should provide generic host/worker/lifecycle facilities and source-inspection host
services. Enterprise should own backend resource lifetime and transport cleanup behind
the provider implementation. This division avoids moving Enterprise infrastructure
into Base and avoids making a provider implementation own the Client's QWidget/QObject
lifecycle.

## Slice 2 handoff constraints

The next slice may introduce the minimal Client-owned public provider/result seam, but
must satisfy all of these constraints:

1. no Base-owned IQA-specific provider/result API;
2. no new Base dependency on concrete IQA Client code;
3. no Client dependency on Enterprise implementation;
4. no production behavior change to menu/dock/result/job/history/inspection flows;
5. no change to the startup/install order recorded above unless separately justified;
6. no change to worker-pool cardinality or ownership merely for abstraction;
7. preserve generation/cancellation/stale-callback and durable-remote-job semantics;
8. existing targeted IQA unit/UI/lifecycle tests remain authoritative and are not
   weakened or broadly rewritten to fit the seam;
9. MAIN remains runnable/testable using public and synthetic inputs only;
10. no production package relocation or dynamic plugin framework in the seam PR.

This characterization is the baseline for reviewing Slice 2. If implementation work
finds that an additional public semantic is truly required, update this document with
the smallest justified extension rather than leaking an Enterprise implementation
detail across the boundary.
