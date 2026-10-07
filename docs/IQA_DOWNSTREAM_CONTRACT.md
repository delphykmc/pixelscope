# IQA downstream consumer and transfer contract

Status: revised downstream contract after Issue #121 Checkpoint C.
Current authority: latest Issue #121 revised Slice 6–8 plan.
Checkpoint C baseline: `main@037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.

The original Slice 5 contract was written before the architecture was revised. Its
useful semantic rules remain: exact MAIN pinning, public port semantics, same-instance
concurrency, lifecycle discipline, path ownership and upstream-first correction of
generic gaps. Earlier assumptions that SUB only supplies a provider beneath a
MAIN-owned final IQA Client, or that real Enterprise proof must precede MAIN cleanup,
are superseded.

## Downstream role

SUB builds an Enterprise IQA extension as a peer consumer of the same MAIN host/public
contracts used by the public reference extension.

```text
MAIN Base/Core + stable host/contracts
          ^                    ^
          |                    |
MAIN reference IQA        SUB Enterprise IQA
(example/mock)            (real product feature)
```

The Enterprise extension may replace every reference-specific UI/workflow choice. It
must not import private helpers from `pixelscope_iqa_reference`.

## Permanent SUB ownership

SUB owns:

```text
src/pixelscope_enterprise/**
tests/enterprise/**
docs/enterprise/**
enterprise/**
```

Those namespaces are reserved from MAIN. SUB may repeatedly merge newer MAIN commits
without an upstream deletion taking ownership of its production files.

SUB should avoid permanent modifications to MAIN-owned files. A required generic
change is requested upstream, implemented in MAIN with public evidence, then consumed
through a newer exact MAIN SHA.

## MAIN surfaces consumed by SUB

The intended dependency surface is small:

- generic `WindowContribution` composition for prepare/dock/action/shutdown;
- optional generic runtime contribution phase when post-window installation is needed;
- bounded `WindowHostAccess` for product-generic selection/source and dock hosting;
- generic `SettingsWindowContribution` / `SettingsPageHost` for extension-owned
  settings pages and validate/save/reset hooks;
- Qt-free `IqaExecutionPort` and `IqaResultAccessPort`;
- normalized public IQA result/job/source/availability types;
- Base worker/lifecycle primitives only when they are genuinely product-generic.

No SUB implementation is required to reuse the MAIN reference widget/controller.
Reference-private symbols are non-contractual.

## Execution and artifact semantics

`IqaExecutionPort` owns the Client-visible control plane: submit, status, terminal
state, optional cancellation and stable result reference. Acceptance-unknown submit
failures must remain explicit and must not be blindly retried.

`IqaResultAccessPort` owns provider-neutral artifact/data access: materialization,
normalized result opening and source resolution. Public locators and diagnostics must
not expose internal storage topology or credentials.

Execution lifetime and result lifetime remain separable. A published result may remain
openable after the live execution controller/process no longer exists.

One provider instance may receive concurrent execution/result/resolution calls. SUB
owns safety for internal sessions, caches, transfers and adapters; the public Client
does not promise per-instance serialization.

## UI and host composition

SUB owns the final detailed IQA panel, controls, job/history presentation, model/server
configuration UX and enterprise diagnostics.

MAIN owns only generic host behavior and public contracts. The MAIN reference IQA
extension is an executable example of menu/dock/lifecycle composition, not a final UI
specification.

An explicit SUB launcher/composition root is sufficient. Dynamic plugin discovery,
hot loading and version negotiation are not required by Issue #121.

## Enterprise configuration

Real Enterprise configuration remains entirely downstream-owned, including server
URLs, storage roots, credentials, SSO/security objects, model configuration, retention
policy and internal path mapping.

MAIN must not gain environment keys or settings schemas merely to support SUB. If a
generic settings contribution point is missing, request that generic host capability
upstream.

## Exact MAIN pin and provenance

Each internal integration/release should record at least:

```text
MAIN_SHA
SUB_SHA_or_revision
public contract/host revision when applicable
internal configuration revision
```

A branch name is not a deployment pin. SUB should merge/fetch the exact approved MAIN
commit and keep its own changes in SUB-owned paths.

The Slice 6 public reference implementation snapshot is identified by its exact merged
MAIN/PR commit history. A separate release tag is optional and must follow the normal
repository tag/release policy; it is not required for architectural transfer.

## Downstream conformance

SUB should maintain internal conformance evidence for its own extension/provider. At a
minimum, validation should cover public state transitions, cancellation capability,
published-result access, normalized result semantics, source resolution, overlapping
same-instance calls, stale callback rejection and clean shutdown.

Real model/server/storage/auth smoke remains an internal release responsibility. Its
success is no longer a prerequisite for MAIN Slice 6–8 architecture work and its
confidential details do not flow back into MAIN.

If real data exposes a semantic gap that the current normalized public contract cannot
represent, report the requirement only. MAIN then decides whether the gap is generic
and adds a public/synthetic regression before SUB consumes the new SHA.

## Lifecycle and resource ownership

Providers remain Qt-free where practical. MAIN host contributions follow existing Qt
ownership and shutdown rules. A SUB extension must not create a new unbounded worker
or thread-pool model merely because it is external.

Issue #81 lifecycle rules remain authoritative. Normal cyclic GC stays enabled for
acceptance validation; GC disabling, arbitrary sleeps, timeout inflation and exception
suppression are not valid fixes.

## Communication boundary

MAIN may flow to SUB with full public source/history/tests/docs.

SUB-to-MAIN feedback contains only company-neutral requirements or observed contract
semantics. It must not include proprietary payloads, credentials, endpoints, private
storage topology, model internals or internal source.

This contract therefore permits MAIN to complete the public host/reference architecture
without inspecting or waiting for the real Enterprise implementation.
