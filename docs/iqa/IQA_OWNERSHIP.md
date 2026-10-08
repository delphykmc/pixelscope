# IQA repository and ownership boundary

Status: Slice 8 public ownership/handoff contract for Issue #121.
Current authority: latest Issue #121 revised Slice 8 plan and `docs/iqa/IQA_HANDOFF.md`.
Checkpoint C baseline: `main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.

This document defines durable source ownership and dependency direction for PixelScope
Base/Core, the public reference/mock IQA extension, and the internal Enterprise IQA
extension. Earlier Slice 0 wording that described MAIN as the permanent owner of the
final IQA Client UI, or described a later Stage 2 move of that Client to SUB, is retained
only in Git history. The revised Issue #121 architecture below supersedes it.

## Post-#137 implementation-scope clarification (planned; not yet code)

The ownership direction established by #121 remains unchanged, but the redesigned operator UX is no longer proposed for reimplementation within the public Reference package. See [MAIN host/Reference Lite plan](IQA_MAIN_HOST_PLAN.md), [server Result contract](IQA_SERVER_RESULT_REQUEST.md) and [temporary-window handoff plan](IQA_HANDOFF_WINDOW_PLAN.md).

- **MAIN Base:** only generic menu/dock/settings/worker/window hosting and public IQA job/result contract, with small incremental changes proved necessary by generic tests.
- **MAIN Reference Lite:** deterministic synthetic request/status/result and independent extension window/lifecycle/build canary. Detailed IQA maps, ROI, chart, report, NPZ reader and portable Save As are *not* public Reference commitments.
- **Temporary public handoff branch:** public-safe production-shaped UX, using exclusively SUB-reserved paths. It is never merged into PUBLIC main.
- **Private SUB:** real IQA extension, server/storage/auth configuration and adapters, complete product UI and packaging.

The existing Reference code and behavior described below are the **as-implemented Slice 8 baseline**, not a mandatory final UX or a claim that Reference Lite refactoring has already happened. Do not introduce IQA-specific status or analysis widgets into Base; a contributed MainWindow job UI is extension-owned. Execution, result publication and analysis window have independent lifetimes.

## Product shapes

The same MAIN Base/Core must support three compositions:

```text
Public Core
PixelScope Base/Core
+ generic extension host
- IQA implementation
```

```text
Public Reference / Mock IQA
PixelScope Base/Core
+ MAIN-owned pixelscope_iqa_reference extension
```

```text
Internal Full
same MAIN Base/Core
+ SUB-owned Enterprise IQA extension
```

The public reference extension demonstrates integration and representative interaction.
It is not the normative Enterprise UI contract.

## Ownership

### MAIN / Base-Core

Base/Core owns product-generic behavior:

- MainWindow, Viewer, Files, Selection, RAW/YUV and common numerics;
- generic menu/dock/settings hosting;
- worker and lifecycle primitives;
- explicit extension composition/contribution contracts;
- bounded public host access required by extensions;
- stable public IQA boundary/result/provider types shared by peer extensions;
- reusable product-generic UI primitives;
- public packaging, documentation and lifecycle validation.

Base must not import or instantiate `pixelscope_iqa_reference` or
`pixelscope_enterprise`.

### MAIN / Reference IQA

The reference package is MAIN-owned and company-neutral. It may:

- contribute its own IQA menu actions and dock/widget;
- exercise mock submission/job/result flows;
- use public/synthetic fixtures such as `FixtureIqaProvider`;
- demonstrate saved/mock result opening and Reference/Scene/result interaction;
- participate in the same Base shutdown lifecycle as any other contribution.

Reference-specific presentation, mock controls and fixture-driving behavior stay inside
the reference namespace. They are examples, not stable APIs for SUB.

### SUB / Enterprise IQA

SUB owns the real IQA feature:

- detailed IQA-specific UI/UX and workflow/controller;
- model/server execution;
- authentication/SSO;
- storage, staging, path mapping and cleanup;
- proprietary request/response schema and result adapter;
- enterprise configuration and diagnostics;
- internal packaging/deployment.

SUB consumes stable MAIN host/contracts. It does not require MAIN to inspect or import
internal source.

## Path ownership

MAIN reference paths and SUB production paths are permanently disjoint.

MAIN reference namespace:

```text
src/pixelscope_iqa_reference/**
tests/iqa_reference/**
docs/iqa/reference/**
```

Reserved SUB namespaces:

```text
src/pixelscope_enterprise/**
tests/enterprise/**
docs/enterprise/**
enterprise/**
```

MAIN must not create, migrate through, or delete files under the reserved SUB
namespaces. In particular, existing public P5 code must not be temporarily moved into a
SUB-owned path and later removed; that would create downstream modify/delete conflicts.

## Dependency direction

The durable dependency graph is:

```text
                 MAIN public host/contracts
                     ^               ^
                     |               |
       Reference / Mock IQA     SUB Enterprise IQA
              MAIN                 internal
```

Allowed:

- Base/Core -> generic Base modules only;
- reference -> stable Base host + public IQA contracts/fixtures;
- Enterprise -> stable Base host + public IQA contracts.

Forbidden:

- Base/Core -> reference implementation;
- Base/Core -> Enterprise implementation;
- Enterprise -> private reference helpers;
- public host contracts -> server/storage/auth-specific semantics.

Public visibility is not sufficient reason to move a concrete IQA implementation into
Base. Host APIs must remain product-generic.

## Public contract ownership

The stable Qt-free boundary currently includes `IqaExecutionPort`,
`IqaResultAccessPort`, normalized `IqaResult`, submission/job/reference/result
types, source locators/resolution, availability/failure semantics and lazy spatial
access. These remain in MAIN because both public reference/conformance code and future
SUB implementations need a common boundary.

Providers do not acquire QWidget/QObject/QThreadPool ownership merely to implement
these ports. Existing concurrency requirements remain authoritative: one provider
instance may receive overlapping calls and must be safe through reentrancy,
thread-safety or internal serialization.

The public boundary describes Client-visible semantics only. It must not contain
Enterprise URLs, storage roots, SSO objects, credentials, proprietary payloads or model
configuration.

## Generic host contract

`WindowContribution` is the explicit window-composition seam. It supports phased
prepare/dock/action/shutdown composition without dynamic discovery. Optional runtime
composition is represented by the generic `RuntimeWindowContribution` phase at the
application composition root.

`WindowHostAccess` is intentionally bounded. An external extension may obtain the
current comparison source slots and register a contributed dock without learning
IQA-specific MainWindow methods. The source tuple preserves comparison-page cardinality:
each page member contributes one `Path | None` slot, so derived/non-native entries are
not silently filtered out.

`SettingsWindowContribution` / `SettingsPageHost` provide the corresponding
product-generic settings seam. An extension may add its own page and validation/save/
reset hooks while keeping its configuration schema and persistence ownership outside
Base.

This is not a marketplace/plugin framework. There is no hot loading, entry-point
discovery or runtime version negotiation.

## Legacy P5 retirement after Slice 8

Historical public P5/Remote-IQA runtime modules, dedicated UI composition, transport,
storage, schema readers, diagnostics, and their P5-specific tests/tools are no longer
part of current MAIN source ownership. The supported public IQA surface is limited to:

- `pixelscope.remote.iqa_domain`;
- `pixelscope.remote.iqa_public_contract`;
- `pixelscope.remote.iqa_public_fixture`;
- `pixelscope_iqa_reference/**` as the explicit public Mock/Reference package.

Base `ApplicationSettings` remains schema v7 and contains no Remote-IQA field or
concrete IQA settings type. Existing schema-v6 `settings/remote_iqa/*` keys are
ignored/preserved by Base migration/reset; MAIN no longer ships a production
interpreter for those historical settings.

The exact pre-extraction implementation snapshot remains
`main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`. Git history plus the Slice 6/7 PRs
is the immutable implementation-archaeology record after source retirement.

## Configuration boundary

MAIN must not require confidential runtime configuration. Real endpoint defaults,
storage topology, credentials, SSO, model configuration and internal environment keys
are SUB-owned.

The reference extension uses only synthetic company-neutral configuration and fixture
data. SUB may define its own untracked environment/config files and tracked examples
inside SUB-owned paths.

## Lifecycle guardrail

Issue #121 does not authorize a new lifecycle model. Issue #81 and
`NATIVE_LIFECYCLE_DIAGNOSTICS.md` remain authoritative.

Ownership separation must not be made to pass by disabling cyclic GC, adding arbitrary
sleeps, inflating timeouts or suppressing exceptions. Contribution shutdown stays
explicit and idempotent; Qt-native ownership and existing worker/thread-pool domains
remain intact unless separately justified and validated.

## MAIN-to-SUB synchronization

SUB consumes exact merged MAIN SHAs. It owns its files under reserved paths and should
not retain permanent patches to MAIN-owned Base files.

When SUB discovers a generic gap, only a company-neutral requirement crosses upstream.
MAIN implements and validates the generic host/contract change using public/synthetic
evidence, merges it, and SUB consumes the newer exact MAIN SHA.

## Revised Slice 6–8 sequencing

Slice 6 proves physical separation in PUBLIC MAIN using the existing public
implementation knowledge and a MAIN-owned reference extension. Real Enterprise
implementation is not a prerequisite.

Slice 7 removes remaining concrete IQA/settings coupling from Base and makes Core-only
and Reference package modes first-class. The default source/package target is Core;
Reference is selected explicitly through `pixelscope-reference`,
`python -m pixelscope_iqa_reference`, or the reference PyInstaller target.

Slice 8 completes the public handoff/conformance/packaging guidance, retires the obsolete
P5 runtime, and keeps only the intentional public Reference package plus stable public contracts.

Real Enterprise integration and internal Full packaging are downstream work. They may
validate the shared contracts, but they do not block MAIN architecture completion.
