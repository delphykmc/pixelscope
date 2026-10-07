# IQA reference extension

Status: Issue #121 Slice 8 supported public Reference/Mock guide.
Baseline before extraction: `main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.

The downstream handoff entry point is `docs/IQA_HANDOFF.md`.\n\nThis directory documents the MAIN-owned reference/mock IQA extension. It is an
executable architecture/reference experience, not the final Enterprise UI.

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
| Transitional IQA/P5 implementation | `ui/iqa_client_install.py`, `ui/iqa_submission.py`, `ui/iqa_workspace.py`, `remote/iqa_explorer.py`, P5 transport/storage/settings/adapters, P5 inspection/history/diagnostics modules | Retained unchanged where practical in Slice 6 as implementation knowledge and compatibility behavior; concrete cleanup is Slice 7. |
| Enterprise production implementation | reserved `pixelscope_enterprise/**` and related SUB paths | Not present or tracked in MAIN. |

The broad legacy families are intentionally not mass-relocated in Slice 6. A relocation
that rewrites dozens of imports/tests before a reference proof would increase lifecycle
and review risk without improving the target dependency direction.

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

Base schema v7 contains no Remote-IQA configuration. Existing public P5 keys are
ignored and preserved by Base; historical P5 tooling uses an extension-owned repository
outside `pixelscope.app` when it needs to interpret or update them.

## Reference behavior

`ReferenceIqaExtension` uses `FixtureIqaProvider` and the public IQA contract to
demonstrate:

```text
launch
-> IQA Reference menu/dock contribution
-> current-pair or synthetic mock submit
-> queued -> running -> completed
-> published mock result open
-> Reference selection
-> Scene selection / lazy spatial access
-> contribution shutdown
```

The File action **Open IQA Reference Result...** creates and opens a deterministic
published mock result. It demonstrates the saved/published-result interaction without
filesystem/server/storage assumptions.

Fixture `advance()` is a reference-development clock only. Enterprise execution
remains defined by `IqaExecutionPort`; SUB must not depend on fixture-private behavior.

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
- shutdown is explicit and idempotent;
- no reference-specific QThreadPool is added;
- no backend job is cancelled implicitly on window close because the synthetic
  reference flow has no external durable resource;
- normal cyclic GC remains the acceptance mode.

This Slice does not alter the characterized P5 thread-pool cardinality or shutdown
order.

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
confidential configuration. Legacy P5 retirement decisions beyond this isolation are
Slice 8 work.
