# IQA reference extension

Status: Issue #139 Reference Lite implementation; Slice 8 history is retained below as provenance.
Baseline before extraction: `main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.

The downstream handoff entry point is `docs/iqa/IQA_HANDOFF.md`.

This directory documents the MAIN-owned reference/mock IQA extension. It is an
executable architecture/reference experience, not the final Enterprise UI.

## Reference Lite behavior (#139)

Issue #139 replaces the Slice 8 text-heavy result/reference/Scene dock with a small optional **integration canary**. See [MAIN Host/Reference cutoff](../IQA_MAIN_HOST_PLAN.md), [server Result contract](../IQA_SERVER_RESULT_REQUEST.md), and [handoff UI plan](../IQA_HANDOFF_WINDOW_PLAN.md).

The MAIN Host needs **no new toolbar/status API** for this layout. Existing `WindowContribution.install_actions/install_dock/shutdown`, the bounded `current_comparison_source_paths()` and QMainWindow's status bar suffice. An opt-in Reference contributes the **File > Run IQA (Synthetic)** command, a **View > Show IQA Mock Jobs** dock, a menu/toolbar-independent job-status notification, and a separately owned non-modal **IQA Analysis Canary** window.

- Each invocation snapshots exactly two native source-path slots in declared order, or explicitly labels the fallback *synthetic pair* when unavailable. The fixture never stages actual files.
- A compact dock lists multiple independent synthetic job IDs. A deliberately manual **Advance Selected Mock Job** test clock drives queued → running → completed/failed with no QTimer, backend thread, sleeps or fabricated production progress; other MainWindow interactions remain enabled.
- **View Selected Result** alone materializes and opens the synthetic published result. Completion never automatically switches the analysis window.
- **Open Empty IQA Analysis Canary** works with no job. The same child QMainWindow reopens when closed, without cancelling queued/running jobs. Closing the owning MainWindow explicitly shuts down the extension.
- **Open Published Synthetic IQA Result (Demo)** creates/completes a fake job and opens its fixture result. It is **not** a filesystem Open/Save As operation; no persistent portable result is produced.
- Result presentation in the child is intentionally limited to identity/count/completeness. No A/B/Map, image reader, ROI/hotspot, NPZ, report, server/storage/auth logic, or official comparative metric is implemented.

### MAIN keyboard focus and menu integration

The Reference launcher contributes three real actions to **File**: Run IQA
(Synthetic), Open Published Synthetic IQA Result (Demo), and Open Empty IQA
Analysis Canary. These actions must occur in the File menu's visible/enabled
QAction list, not only in the MainWindow's internal action map. View > Show IQA
Mock Jobs is independently contributed to View. The generic Session composition
replaces the File menu after initial MainWindow action installation. That
replacement **must transfer every existing contributed QAction in order**, rather
than rebuilding from a hardcoded list of Base commands, and update `_menu_map`
to the newly attached menu. The Reference regression checks the active menu-bar
membership and the visible File popup after full presentation composition.
When debugging launcher differences, check the explicit
`python -m pixelscope_iqa_reference` entry point and the currently running
executable/version; the Core-only launcher does not install Reference actions.

The generic MAIN Files tree exclusively owns keyboard **Delete** and **Ctrl+A**.
The native `DocumentListWidget.keyPressEvent` consumes unmodified Delete and
emits the same `remove_changing` / `remove_requested` signals as its context
menu; a Files-owned `WidgetWithChildrenShortcut` handles Ctrl+A. The Delete
QShortcut was intentionally removed because the Qt item view can consume that
key before shortcut activation. A focused IQA Jobs list must never remove
already selected PixelScope images, nor change the background Files selection.
Explicit Edit > Remove Selected and Selection > Select All menu commands remain
available. Other existing
application-wide navigation shortcuts (for example image/page arrows and
number keys) are not changed in this scope: their focus behavior should be
reviewed separately before changing established viewer navigation.

The actual IQA client execution and result workflows, async scheduling, and full A/B/Map Analysis Window remain **SUB-owned**. Reference's fixture `advance()` is a deterministic UI conformance clock, never a scheduler contract. The child window is parented to the owning MainWindow as a top-level Qt window with extension-owned references and teardown; no new generic host API is required.

### Targeted validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\iqa_reference\test_reference_extension.py
.\.venv\Scripts\python.exe -m pytest -q tests\conformance\test_iqa_provider_handoff.py
.\.venv\Scripts\python.exe scripts\check_docs.py
.\.venv\Scripts\python.exe -m ruff check src\pixelscope_iqa_reference tests\iqa_reference
.\.venv\Scripts\python.exe -m ruff format --check src\pixelscope_iqa_reference tests\iqa_reference
```

Qt visual/native shutdown behavior and Core/Reference release-build isolation still require owner-local Windows validation. Do not promote an unrun build/pytest to a PASS claim.

## Source-level compositions

Core-only composition is:

```python
window = MainWindow(window_contributions=())
compose_main_window_presentation(window)
```

Reference composition is:

```python
extension = ReferenceIqaExtension()
window = MainWindow(window_contributions=(extension,))
compose_main_window_presentation(window)
```

Both compositions are first-class source entry points:

```powershell
.\.venv\Scripts\pixelscope.exe
.\.venv\Scripts\pixelscope-reference.exe
# equivalent module forms:
.\.venv\Scripts\python.exe -m pixelscope
.\.venv\Scripts\python.exe -m pixelscope_iqa_reference
```

The default `pixelscope` entry point is Core-only. Historical P5 composition is never
selected implicitly.

## Slice 6 ownership classification

The pre-extraction mixed implementation was classified by semantic ownership rather
than by its current file location.

| Category | Current modules/surfaces | Slice 6 disposition |
|---|---|---|
| Base/Core generic | `app/main_window.py`, `app/window_contribution.py`, worker/lifecycle primitives, menu/dock persistence | Remain in `pixelscope/**`; generic bootstrap/runtime contribution and bounded source-path access are completed here. |
| Public boundary contract | `remote/iqa_public_contract.py`, normalized IQA domain types and public fixture/conformance support | Remain in MAIN and are shared by reference and future Enterprise peers. |
| MAIN reference implementation | New `pixelscope_iqa_reference/**` | Owns example/mock dock, actions, job controls, result/reference/Scene presentation and fixture driving. |
| Historical P5 implementation | Pre-extraction P5 UI/transport/storage/schema/history runtime | Retired from current MAIN source in Slice 8 after the public contract/reference handoff was fixed; preserved through exact Git history. |
| Enterprise production implementation | reserved `pixelscope_enterprise/**` and related SUB paths | Not present or tracked in MAIN. |

Slice 6 intentionally kept the legacy families until the Reference proof existed.
Slice 8 removes those obsolete runtime families instead of relocating them into another
MAIN namespace. The exact pre-extraction SHA remains the implementation reference.

## Generic host additions

`WindowContribution` remains the window phase contract. Slice 6 adds two small generic
surfaces:

- `WindowHostAccess.current_comparison_source_paths()` for bounded, slot-preserving
  source-selection access without IQA-specific MainWindow methods; each comparison-page
  member contributes one slot and derived/non-native members are represented by `None`;
- `RuntimeWindowContribution.install_runtime()` for explicit post-window runtime
  composition at the same lifecycle point previously occupied by concrete IQA setup.

`pixelscope.app.bootstrap` owns common application/presentation composition and imports
no IQA implementation. Concrete launchers select extensions explicitly.

No discovery registry, entry points, marketplace, hot loading or version negotiation
framework is introduced.

Slice 6 also adds a product-generic settings contribution seam:
`SettingsWindowContribution` may add an extension-owned page through
`SettingsPageHost` with optional validate/save/reset hooks. The extension owns the
page semantics and persistence behind those hooks; Base does not gain an Enterprise
schema or IQA-specific setting.

Base schema v7 contains no Remote-IQA configuration. Existing public P5 keys remain
unknown extension data to Base and are preserved by migration/reset; current MAIN no
longer ships P5 tooling that interprets them.

## Slice 8 Reference behavior (historical, superseded by #139)

Prior to Reference Lite the optional mock workspace included Reference and Scene comboboxes, first-attribute-only text detail, and an **Open IQA Reference Result...** action that generated a mock published result. These features were never normative Enterprise UX and are intentionally retired from the live Reference UI. The public `FixtureIqaProvider`, `IqaExecutionPort`, result conformance and synthetic fixtures remain intact. The previous exact source can be inspected in Git history at the merged #142 baseline `e8959eaa27acc0777542f33a8bf476e3ec6ad28c`.

## Dependency rule

The reference package may import only stable/generic MAIN surfaces required to compose
and exercise the public contract. It must not import:

- `pixelscope.ui.iqa_client_install` or private legacy Client helpers;
- P5 transport/storage/settings modules;
- `pixelscope_enterprise`;
- confidential configuration.

Architecture tests enforce Base/Core not importing the reference/Enterprise namespaces
and constrain the reference package's MAIN imports.

## Lifecycle and resources

The reference contribution follows existing MainWindow contribution ownership:

- the window/Qt hierarchy owns the dock and widget;
- the extension holds the window through `weakref.ref`;
- shutdown is explicit and idempotent, including the separately owned analysis canary;
- no reference-specific QThreadPool, asynchronous timer or backend resource is added;
- closing the child only hides the canary, never cancels a mock job;
- owner shutdown disconnects the widget/action callbacks and disposes the child window;
- normal cyclic GC remains the acceptance mode.

The historical P5-specific worker/thread-pool implementation is retired. Issue #81
lifecycle coverage remains through generic TaskWorker and contributed-dock canaries.

## Snapshot and migration evidence

The exact mixed implementation immediately before Revised Slice 6 is
`037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`. It remains permanently inspectable in Git
history together with PR #126 (synthetic fixture) and PR #128 (composition/lifecycle
seam).

The Slice 6 PR records the extracted reference implementation and its exact HEAD. No
release tag is created solely for this refactor; tag creation remains subject to the
normal release/tag policy.

## Public package targets

The canonical Windows release remains the Core target:

```powershell
.\.venv-release\Scripts\python.exe scripts\build_release.py --target core
```

The public mock/reference target is built explicitly:

```powershell
.\.venv-release\Scripts\python.exe scripts\build_release.py --target reference
```

Core excludes the reference and Enterprise namespaces. Reference uses the same Base
and public contracts plus `pixelscope_iqa_reference`; neither target requires
confidential configuration. Historical P5 runtime code is retired from current MAIN
source as part of Slice 8.
