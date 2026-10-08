# PixelScope IQA — documentation map

**Current authority:** post-Issue #121 peer extension ownership, with proposed post-UX-discovery plans tracked by #139, #140, #141 and Draft PR #142. **Do not use the historical P5 / Remote-IQA specifications below to implement the new IQA client.**

## Current MAIN contracts (implemented)

- [IQA ownership / dependency boundary](IQA_OWNERSHIP.md) — PUBLIC MAIN Base/Reference vs PRIVATE SUB Enterprise, immutable MAIN/SUB path ownership
- [IQA handoff and public conformance](IQA_HANDOFF.md) — stable host/provider API, baseline and transfer validation
- [Downstream contract](IQA_DOWNSTREAM_CONTRACT.md) — SUB peer extension, public port semantics and exact MAIN SHA
- [Enterprise SUB setup guide](IQA_ENTERPRISE_SUB_GUIDE.md) — company-neutral bootstrap, legacy test recovery, internal integration
- [Current Reference implementation guide](reference/README.md) — *as implemented* Slice 8 optional public mock; not the final IQA UX

## Proposed changes (not yet implemented)

- [MAIN Host/Reference Lite cutoff](IQA_MAIN_HOST_PLAN.md) — Issue #139; explicitly narrows public Reference role
- [Server Result/JSON/NPZ interface request](IQA_SERVER_RESULT_REQUEST.md) — Issue #140; **server negotiation proposal**, not a frozen wire/storage schema
- [Temporary public-safe IQA Window implementation/handoff plan](IQA_HANDOFF_WINDOW_PLAN.md) — Issue #141; implementation will take place separately on an unmerged SUB-owned handoff branch

These plans do **not** change the runtime, modify a server, or create an Enterprise implementation branch merely by being documented.

## Historical records — DO NOT treat as live contract

[Legacy P5/Remote-IQA archive](legacy/README.md) contains immutable-history-oriented migration references such as `REMOTE_IQA_V1_SPEC.md`, `REMOTE_IQA_V2_SPEC.md`, Remote-IQA Viewer/History/Integration characterization, and early #121 boundary characterization. Their original terms like "current", "normative", "production", or "server owns..." mean **the P5 baseline at that historical moment**, *not* the current public runtime or future Enterprise server contract.

Historical implementation and tests have been retired from PUBLIC MAIN source; inspect the exact historical SHAs from the handoff guide only for archaeology. Do not reintroduce historical storage trees, schema v1/v2 rules, Viewer mutation, client-owned production UI, Reference-dependent computation or internal endpoint assumptions without a new explicit design decision.

## Related documentation

- [Repository-wide documentation index](../index.md) (minimal root routing only)
- [User Guide IQA Reference feature](../user-guide/features/iqa-workspace.md) — documents the currently shipped optional Reference UI; changed product UX belongs in a later implementation PR
- [Historical execution plans](../exec-plans/completed/p5-remote-iqa-platform-through-p5f.md) — retained development rationale, not new implementation instructions
