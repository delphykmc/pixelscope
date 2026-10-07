# IQA repository and ownership boundary

Status: revised post-Checkpoint-C ownership contract for Issue #121.
Current authority: latest Issue #121 revised Slice 6–8 plan.
Checkpoint C baseline: `main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.

This document defines durable source ownership and dependency direction for PixelScope
Base/Core, the public reference/mock IQA extension, and the internal Enterprise IQA
extension. Earlier Slice 0 wording that described MAIN as the permanent owner of the
final IQA Client UI, or described a later Stage 2 move of that Client to SUB, is retained
only in Git history. The revised Issue #121 architecture below supersedes it.

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
docs/iqa_reference/**
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
current comparison source paths and register a contributed dock without learning
IQA-specific MainWindow methods.

`SettingsWindowContribution` / `SettingsPageHost` provide the corresponding
product-generic settings seam. An extension may add its own page and validation/save/
reset hooks while keeping its configuration schema and persistence ownership outside
Base.

This is not a marketplace/plugin framework. There is no hot loading, entry-point
discovery or runtime version negotiation.

## Current transitional P5 code

Checkpoint C left the existing public P5/Remote-IQA implementation in
`src/pixelscope/**` as a compatibility path. Slice 6 preserves it deliberately while
proving the new peer-extension direction with `pixelscope_iqa_reference`.

Physical location of that legacy code does not redefine target ownership. Concrete P5
transport/storage/settings/detailed IQA presentation remain transitional and are
candidates for Slice 7 cleanup after equivalent reference behavior and architecture
proof exist.

The exact pre-extraction implementation snapshot is
`main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`. No ad-hoc release tag is required
for Slice 6; exact Git history plus the Slice 6 PR/HEAD provides immutable reference
evidence.

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
and Reference package modes first-class.

Slice 8 completes the public handoff/conformance/packaging guidance and decides which
legacy/reference runtime material remains supported.

Real Enterprise integration and internal Full packaging are downstream work. They may
validate the shared contracts, but they do not block MAIN architecture completion.
