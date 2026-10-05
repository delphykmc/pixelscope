# IQA repository and ownership boundary

Status: accepted staged ownership contract for Issue #121 Slice 0.
Baseline: `main@6958e2fa3770137f80de3599532cd0141c99b868`.

This document is the repository authority for the staged **Base + IQA Client +
Enterprise IQA** ownership model. It defines repository/source ownership and allowed
dependency direction. It does **not** replace the existing runtime, numerical, result,
transport, settings, or Qt lifecycle contracts in `ARCHITECTURE.md`,
`REMOTE_IQA_CONTRACT.md`, `REMOTE_IQA_V2_SPEC.md`, or `DECISIONS.md`.

Slice 0 is documentation/harness only. Existing production composition remains
unchanged until later Issue #121 slices characterize and introduce the required seams.

## Repository roles

### MAIN

The public/external PixelScope repository is the authoritative upstream for common
application behavior and, during Stage 1, the public IQA Client. MAIN must remain
implementable, runnable, and deterministically testable without confidential
infrastructure or source.

### SUB

The internal enterprise repository consumes MAIN and owns confidential/company-only
IQA implementation and deployment. SUB may adapt internal systems to public MAIN
contracts, but MAIN must never require SUB-only knowledge to build, test, or run its
public/synthetic paths.

Information flow is effectively one-way from MAIN to SUB at source level. Internal
findings may be reported back as public requirements, data-shape constraints, or
behavioral semantics, but not as confidential source, credentials, proprietary raw
payloads, model internals, or internal-only infrastructure details.

## Logical layers and dependency direction

The **target dependency rule for new work** is:

```text
Enterprise IQA -> IQA Client -> PixelScope Base
```

The arrow means **depends on**. Therefore:

- Base must not acquire a new dependency on IQA Client or Enterprise IQA.
- IQA Client may depend on public Base host/composition/contribution/lifecycle
  contracts.
- Enterprise IQA may depend on the public IQA Client provider/result/domain contract
  and on public Base contracts exposed through the Client/host integration boundary.
- MAIN must not import, instantiate, configure, or otherwise require Enterprise-only
  implementation.

Current production code still contains concrete Base/IQA coupling documented in
Issue #121. Slice 0 does not claim that the target direction is already mechanically
enforced. Later slices must characterize and reduce that coupling without increasing
reverse dependencies in the meantime.

## Contract ownership rule

The interface is owned by the layer that consumes its semantics, not by the layer that
implements it.

For Issue #121 this means:

- **Base** owns only generic application host/composition/contribution/lifecycle
  contracts. Base does not own an IQA-specific provider or IQA result/domain API.
- **IQA Client** owns the IQA-specific provider/result/domain contract it consumes.
  The planned `IqaProvider` / result-source protocol therefore belongs to the IQA
  Client boundary.
- **Enterprise IQA** implements or adapts that Client-owned contract using internal
  infrastructure.

This is deliberate dependency inversion. The Client defines what IQA capability it
needs; synthetic and Enterprise implementations satisfy the same Client-owned port.
Keeping `IqaProvider` out of Base also allows the future Stage 2 move of IQA Client to
SUB without forcing an IQA-specific API to remain in Base.

## Stage 1 — current target

Stage 1 deliberately keeps Base and IQA Client in MAIN while making their ownership
and dependency boundary explicit.

```text
MAIN repository

PixelScope Base
  - MainWindow / Viewer / Core / IO
  - common menu, dock, settings host
  - worker/lifecycle primitives
  - generic host/composition/contribution contracts
           ^
           | depends on
IQA Client
  - IQA workspace UI and visualization
  - IQA-specific menu/dock contribution
  - generic IQA controller/state machine
  - result/reference/scene/history presentation
  - client-side async/lifecycle behavior using Base primitives
  - public IqaProvider / IQA result/domain contracts
  - synthetic/fixture provider for deterministic development
           ^
           | implements/adapts Client-owned IQA contracts
SUB repository

Enterprise IQA
  - real inference/model implementation
  - real internal server and transport details
  - internal storage/path conventions
  - authentication/secrets/security integration
  - proprietary response/schema adapter
  - enterprise configuration
  - internal packaging/deployment
```

### Base-owned

Base owns common application behavior that is useful and testable independently of a
confidential IQA backend:

- image loading and RAW/YUV semantics;
- core numerics;
- Files / Selection / Viewer / Statistics / Histogram / Difference;
- `MainWindow` shell and common layout;
- menu taxonomy, ordering, styling, and generic contribution points;
- generic dock hosting and workspace persistence;
- common settings shell;
- worker and lifecycle primitives;
- public packaging/release and documentation build;
- stable public host/composition/contribution/lifecycle contracts intended for
  clients/extensions.

Base must not define an IQA-specific `IqaProvider`, IQA result schema/domain API, or
Enterprise adapter merely because those types are public. Public visibility does not
make an IQA-specific contract Base-owned.

### IQA Client-owned during Stage 1

The public Client owns presentation and client behavior that can be developed against
public contracts and synthetic data:

- IQA workspace UI and visualization;
- IQA-specific menu/dock contributions;
- generic IQA controller/state machine;
- result exploration, reference selection, scene navigation, and history presentation;
- client-side async/lifecycle behavior built on Base primitives;
- the IQA-specific `IqaProvider` / result-source protocol consumed by the Client;
- stable public IQA result/domain types used by Client presentation and state;
- deterministic synthetic fixtures/providers implementing those same contracts for
  development and validation.

The Client contract should expose only capability and data semantics required by the
Client. It should remain Qt-free where practical so a provider implementation does not
need to create or manage QWidget/QObject/QThreadPool objects merely to supply IQA data.

### Enterprise-owned

SUB owns implementation that cannot be correctly implemented or validated without
confidential infrastructure or internal knowledge:

- real model/inference implementation;
- internal server and transport implementation details;
- internal storage and path conventions;
- authentication, secrets, and security integration;
- proprietary response/schema details;
- an `EnterpriseIqaProvider` or equivalent adapter that implements the Client-owned
  `IqaProvider` contract;
- mapping from proprietary enterprise responses into public Client-owned IQA
  result/domain types;
- enterprise configuration;
- internal packaging, deployment, and internal-only documentation.

Enterprise may depend on the Client contract; the Client must not depend on the
Enterprise implementation.

## No-confidential-runtime requirement for MAIN

MAIN is not allowed to require confidential runtime inputs for its supported public
and synthetic development path. In particular, MAIN must not require:

- SUB source code or private packages;
- internal-only servers or network routes;
- credentials, tokens, secrets, or security configuration;
- proprietary models or datasets;
- private storage conventions or mount topology;
- confidential raw server payloads or schemas;
- company-specific fixture values that disclose internal implementation details.

Public contracts may describe only the semantics needed by the Client. Synthetic
fixtures may encode public characteristics such as cardinality, scalar/per-scene/grid
shape, range/direction semantics, missing/partial values, lifecycle states, and large
stress shapes. They must remain company-neutral and must not copy a confidential raw
payload merely to make an external test pass.

A capability belongs in MAIN only when it can be implemented and deterministically
validated using public PixelScope contracts and public/synthetic data. If correct
implementation or validation requires confidential infrastructure, APIs, models,
datasets, credentials, or internal-only knowledge, ownership belongs in SUB.

## Stage 2 — future ownership target

When SUB has sufficiently capable development/review/agent access, ownership may move
to:

```text
MAIN: PixelScope Base + stable extension/host API
SUB:  IQA Client + Enterprise IQA as an extension
```

Because `IqaProvider` and the public IQA result/domain types are Client-owned, they move
with IQA Client in Stage 2. Base retains only its generic host/composition/contribution
contracts and therefore does not require an IQA-specific compatibility surface after
the ownership transfer.

Stage 1 must therefore avoid decisions that force another application-architecture
rewrite when IQA Client ownership moves. The intended Stage 2 transition is primarily
an ownership/package relocation across a stable Base host contract.

A useful exit criterion is that removing IQA Client from production composition does
not require redesigning Base behavior.

## Compatibility and lifecycle guardrail

Issue #121 does not authorize lifecycle redesign. Existing P5/R composition and Issue
#81 Qt/worker lifetime contracts remain authoritative until a later slice proves a
specific change is necessary.

In particular, ownership separation must not by itself introduce:

- a new thread pool;
- a new QObject/QWidget ownership model;
- dynamic plugin discovery, hot loading, entry points, or version negotiation;
- broad import/path moves before the first enterprise handoff;
- broad rewrites of existing synthetic IQA or lifecycle tests.

Adapters, explicit seams, and compatibility shims are preferred when they preserve
current behavior and reduce lifecycle churn.

## Agent and review decision checklist

Before changing Base/IQA/Enterprise-adjacent code, answer these questions:

1. Can the capability be implemented and validated using only public contracts and
   synthetic/public data? If yes, MAIN may own it during Stage 1; otherwise it belongs
   in SUB.
2. Is the contract generic application-host behavior, or is it semantically IQA?
   Generic host/composition/contribution/lifecycle contracts belong to Base;
   `IqaProvider` and IQA result/domain contracts belong to IQA Client.
3. Does the change add a Base dependency on concrete IQA Client code or an IQA Client
   dependency on Enterprise implementation? If yes, stop and redesign the boundary.
4. Would MAIN fail to build, start, test, or exercise the public Client without SUB,
   internal network access, credentials, private models, or proprietary payloads? If
   yes, the change violates the boundary.
5. Does a fixture reproduce confidential raw payload structure when a smaller public
   semantic contract would suffice? If yes, replace it with a company-neutral fixture.
6. Does the proposed separation alter Qt ownership, shutdown order, worker pools,
   cancellation/quiescence, or stale-callback behavior? If yes, treat it as a separate
   lifecycle-sensitive change and validate against the existing authoritative
   contracts rather than folding it into ownership cleanup.

## Issue #121 slice sequencing

This contract intentionally precedes runtime changes:

- **Slice 0:** ownership/dependency contract only; no runtime changes.
- **Slice 1:** characterize and freeze current concrete IQA imports, settings, tests,
  provider surface, and production install/shutdown order.
- **Slice 2+:** introduce the minimum Client-owned IQA provider/result seam and the
  generic Base composition seam while preserving current behavior and lifecycle
  contracts.

Later slices may refine implementation detail, but they must preserve the ownership
and one-way dependency rules here unless the owner explicitly records a superseding
architecture decision.

The [downstream consumer and transfer contract](IQA_DOWNSTREAM_CONTRACT.md) records
the Slice 5 semantic draft, SUB path/pin/sync policy and conformance/smoke plans.
It awaits merged Slice 2 reconciliation and does not certify transfer readiness.
