# IQA downstream handoff and conformance kit

Status: Issue #121 MAIN architecture and Slice 8 handoff completed.
Slice 8 merged MAIN snapshot: `main@19cf5d395fb86c62d55a28355e3beb147f5dd8bf` (PR #133).
Slice 8 starting baseline (merged Slice 7): `main@29561bdb70e722380a8041212d991ae21b72c6be`.
Pre-extraction mixed implementation snapshot:
`main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.
For the SUB agent's first implementation plan, repository layout, test migration, and
validation commands, start with `docs/IQA_ENTERPRISE_SUB_GUIDE.md`.
That guide is public and contains no enterprise-specific configuration.

This document is the single public handoff entry point for an external IQA extension.
It does not describe a specific Enterprise implementation. It defines what MAIN owns,
what a downstream repository may depend on, what it must validate, and how newer MAIN
revisions are consumed without permanent downstream patches to MAIN-owned files.

## Post-UX-discovery implementation plan (specification; pending code)

After #137, the proposed division is **MAIN generic host + small Reference Lite integration canary**, with actual A/B/Map IQA Analysis Window work developed on a temporary public-safe, NON-MERGED SUB-owned handoff branch, then transferred to PRIVATE SUB. The historical Reference UX documented in this file reflects the current implementation and is not an approved product layout.

See [MAIN scope and generic host requirements](IQA_MAIN_HOST_PLAN.md), [server JSON/NPZ/result publication request](IQA_SERVER_RESULT_REQUEST.md) and [temporary IQA Window implementation/handoff](IQA_HANDOFF_WINDOW_PLAN.md), tracked by #139, #140, #141. These specifications do not themselves change source code, bump the public contract revision or create the implementation branch.

Public Core must not acquire a product-specific Job registry, A/B/Map UI or enterprise artifact parser. Existing `WindowContribution` and `WindowHostAccess` should be tested before adding any generic toolbar/status/lifecycle hooks. The enterprise extension owns the MainWindow-contributed Run/Status/View action and the independent non-modal Analysis Window. MAIN Reference only needs to prove extension composition, public job-state semantics, child-window lifecycle, clean shutdown and packaging. Any needed normalized official pair-comparison contract addition is a narrowly reviewed public MAIN change, never a private server wire schema.

## Stable host surface

The supported host seam is intentionally small:

- `pixelscope.app.window_contribution.WindowContribution`
  - `prepare(window)`
  - `install_dock(window)`
  - `install_actions(window, menu_name, add_action)`
  - `shutdown()`
- `RuntimeWindowContribution.install_runtime(window)` for explicit post-window
  runtime composition when required;
- `WindowHostAccess.current_comparison_source_paths()` for one
  `Path | None` slot per current comparison-page member;
- `WindowHostAccess.register_contributed_dock()` for Base persistence/shutdown
  ownership of a contributed dock;
- `SettingsWindowContribution` / `SettingsPageHost` for extension-owned settings
  pages with validate/save/reset hooks.

MAIN does not provide dynamic discovery, hot loading, a plugin marketplace, or runtime
version negotiation. An explicit downstream launcher/composition root is sufficient.

## Public IQA contract

The Qt-free provider boundary is
`pixelscope.remote.iqa_public_contract`.

The current compatibility identifier is:

```text
IQA_PUBLIC_CONTRACT_REVISION = 1
```

Revision rules:

- additive, source-compatible changes are preferred and do not require a revision bump;
- a breaking semantic or signature change increments the revision;
- a breaking change must be called out in Issue/PR/release documentation;
- exact MAIN SHA remains the authoritative integration pin even when the revision is
  unchanged;
- downstream conformance evidence records both the exact MAIN SHA and the public
  contract revision.

The public ports are:

- `IqaExecutionPort`: submit/status/result-reference/cancel;
- `IqaResultAccessPort`: materialize/open-result/source-resolution;
- normalized `IqaResult` and related job/result/source/availability types;
- lazy spatial access through `IqaSpatialAccess`.

Provider-only transport, storage topology, authentication, proprietary payloads and
model configuration stay behind those ports.

## Reference extension layout

The supported public example is:

```text
src/pixelscope_iqa_reference/**
tests/iqa_reference/**
docs/iqa_reference/**
```

It is a peer consumer of the same MAIN host/contracts expected to be consumed by a
downstream Enterprise extension. It is not a private helper library for downstream
code and it is not the normative final IQA UI.

The reference extension demonstrates:

```text
explicit composition
-> contributed action/dock
-> current-pair or synthetic submit
-> queued -> running -> completed
-> published result open
-> Reference / Scene selection
-> lazy spatial access
-> explicit contribution shutdown
```

## Explicit composition example

A downstream composition root follows the same shape as the reference launcher:

```python
app = create_application()
repository, settings, performance = load_startup_settings()
extension = EnterpriseIqaExtension(...)

window = MainWindow(
    settings,
    performance,
    repository,
    window_contributions=(extension,),
)
compose_main_window_presentation(
    window,
    runtime_contributions=(extension,) if needs_runtime_phase else (),
)
window.show()
raise SystemExit(app.exec())
```

The default MAIN `pixelscope` launcher stays Core-only. The public
`pixelscope-reference` launcher opts into the MAIN reference package explicitly.

## UI ownership

MAIN owns generic host behavior:

- menu insertion;
- dock hosting/persistence;
- generic settings hosting;
- generic worker/lifecycle primitives;
- product-generic Viewer/Files/Selection/RAW/YUV behavior.

Downstream owns the final detailed IQA UI/UX, job/history presentation,
model/server/configuration controls, diagnostics and internal workflow choices.

A reference UI choice is illustrative only unless the public host/contract explicitly
defines the behavior.

## Lifecycle and shutdown rules

Issue #81 remains authoritative.

A downstream contribution must:

- keep normal cyclic GC enabled;
- use explicit, idempotent shutdown;
- respect Qt parent/child ownership;
- avoid arbitrary sleeps, timeout inflation or exception suppression as lifecycle fixes;
- avoid introducing an unbounded or competing thread-pool ownership model without a
  separately justified MAIN contract change;
- reject stale callbacks/results after their owner is no longer active.

The MAIN reference extension intentionally adds no new provider thread pool.

## Concurrency rules

One provider instance may receive overlapping calls.

The Client does not promise per-instance serialization for:

- execution calls;
- result materialization/opening;
- source resolution;
- lazy spatial access.

A provider must therefore be thread-safe/reentrant or serialize internally.
Acceptance-unknown submission failures use
`IqaProviderErrorKind.AMBIGUOUS_SUBMIT` and must not be blindly resubmitted.

## Configuration ownership

Enterprise configuration is downstream-owned.

MAIN must not receive:

- real endpoints;
- credentials/tokens;
- SSO/security objects;
- proprietary storage topology;
- internal model configuration;
- secret environment variables;
- proprietary request/response schemas.

A downstream repository may maintain its own tracked example schema and untracked local
configuration inside downstream-owned paths.

## Public conformance kit

MAIN provides company-neutral conformance evidence at:

```text
tests/conformance/test_iqa_provider_handoff.py
tests/iqa_reference/test_reference_extension.py
tests/ui/test_issue121_extension_settings.py
tests/unit/test_issue121_iqa_reference_architecture.py
tests/unit/test_iqa_public_contract.py
tests/unit/test_issue121_public_package_modes.py
```

The dedicated handoff suite exercises only the public provider contract plus the
synthetic `FixtureIqaProvider`. A downstream repository can copy/mirror that suite and
replace the synthetic provider factory with its own provider plus an internal mechanism
that deterministically drives a test job to terminal state.

Minimum downstream evidence:

- protocol compatibility;
- queued/running/terminal state semantics;
- cancellation capability semantics;
- stable published-result reference;
- materialize/open normalized result flow;
- explicit unavailable/partial/failure states;
- lazy spatial access;
- source-resolution availability semantics;
- same-instance overlapping calls;
- sanitized public errors/diagnostics;
- stale callback rejection;
- clean extension shutdown.

Real model/server/auth/storage smoke is additional downstream release evidence, not a
MAIN acceptance dependency.

## Exact MAIN SHA sync procedure

Downstream integration uses an exact approved MAIN commit, never a branch name as the
deployment pin.

Recommended flow:

```text
record current SUB revision
fetch MAIN
verify target MAIN SHA
merge/rebase according to internal repository policy
run downstream conformance
run internal product smoke
record MAIN_SHA + SUB_SHA/revision + contract revision + config revision
```

If the downstream extension discovers a generic host/contract gap, report only the
company-neutral requirement upstream. MAIN adds a public/synthetic regression and
merges a newer exact SHA; downstream then consumes that SHA.

## Forbidden downstream patch policy

Permanent downstream modifications to MAIN-owned paths are not part of the supported
architecture.

Reserved downstream ownership remains:

```text
src/pixelscope_enterprise/**
tests/enterprise/**
docs/enterprise/**
enterprise/**
```

MAIN will not create or later delete files in those namespaces.

A temporary local diagnostic patch to MAIN-owned code must either be discarded or
converted into a generic upstream change before an internal release is considered
conformant.

## Packaging shapes

Three product shapes are intentional:

```text
Public Core
  MAIN Base/Core only

Public Reference
  same MAIN Base/Core
  + pixelscope_iqa_reference

Internal Full
  same approved MAIN Base/Core SHA
  + downstream Enterprise extension
```

Public build commands:

```powershell
.\.venv-release\Scripts\python.exe scripts\build_release.py --target core
.\.venv-release\Scripts\python.exe scripts\build_release.py --target reference
```

Internal packaging is downstream-owned. Its provenance records at least:

```text
MAIN_SHA
SUB_SHA_or_revision
IQA_PUBLIC_CONTRACT_REVISION
internal_configuration_revision
```

## Immutable reference and migration evidence

The mixed public implementation before physical extraction remains inspectable at:

```text
main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07
```

Slice 7's completed public Core/Reference package baseline is:

```text
main@29561bdb70e722380a8041212d991ae21b72c6be
```

Exact Git commits and merged PR history are the immutable transfer record. A dedicated
tag is optional and must follow the repository's normal release/tag policy.

## Reference and legacy retirement rule

`pixelscope_iqa_reference` remains supported because it is the public executable
example and conformance peer.

Historical P5/Remote-IQA runtime code under `pixelscope/**` is not a production
dependency of Core or Reference after Slice 7. Slice 8 retires that implementation from
normal MAIN source ownership after the handoff/conformance material above protects the
public host and provider semantics.

The supported MAIN IQA source boundary after retirement is intentionally small:

```text
src/pixelscope/remote/iqa_domain.py
src/pixelscope/remote/iqa_public_contract.py
src/pixelscope/remote/iqa_public_fixture.py
src/pixelscope_iqa_reference/**
```

Historical P5 transport/storage/schema-v1/v2/result-explorer/UI/runtime implementations
and their dedicated test/tooling families are recoverable from immutable MAIN history,
especially `037fda2dc3e79475b5ba1841e8308bbbe5d0cd07` and the Slice 7 merged baseline
`29561bdb70e722380a8041212d991ae21b72c6be`. They are no longer supported public
runtime APIs.

No legacy P5 tests were copied to `tests/enterprise/**` as part of Issue #121.
The 43 retired test files remain in the Slice 7 Git snapshot, **not** in current
MAIN's working tree or a new archive directory. The SUB agent must inventory and
selectively migrate their still-relevant behavioral assertions; do not copy the
obsolete P5 import graph back into MAIN. See
`docs/IQA_ENTERPRISE_SUB_GUIDE.md` for exact recovery commands and the file list.

Retirement must not weaken Issue #81 lifecycle canaries, public contract coverage, or
the two public package targets.


Slice 8 retires the old product-facing P5/Remote-IQA diagnostic and preflight CLI entry
points from `scripts/`. Their historical implementations remain available from the
pre-extraction and Slice 7 Git history. Public validation now uses the provider-neutral
handoff conformance suite and the supported Reference package instead of P5-specific
server/storage diagnostic commands.
