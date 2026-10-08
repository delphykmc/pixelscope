# Enterprise IQA SUB bootstrap and legacy-test migration

Status: public MAIN-to-SUB implementation guide after Issue #121 (completed Slice 0–8).
Authority: [IQA handoff](IQA_HANDOFF.md), [downstream contract](IQA_DOWNSTREAM_CONTRACT.md),
and [Issue #121](https://github.com/delphykmc/pixelscope/issues/121).
This file is MAIN-owned, company-neutral guidance, **not** an Enterprise implementation,
release authorization, or a statement about the private SUB repository's current state.

## What Issue #121 accomplished

The objective was to separate **source ownership and dependency direction**, not
to transplant a ready-to-run proprietary IQA app or all historical P5 tests into a
private repository. Public MAIN must remain useful, buildable and testable without
any internal resources; the eventual real feature is entirely SUB-owned.

```text
PUBLIC MAIN
  PixelScope Core (Viewer / Files / RAW / YUV / generic hosts)
      + Qt-free public IQA contract
      + optional pixelscope_iqa_reference (synthetic UX/provider)
                 ^                     ^
                 | public host/contracts|
                 +---------------------+
                                       |
PRIVATE SUB                         Enterprise IQA extension
  same exact MAIN Core revision       (real UI/workflow/provider/result adapter)
  + src/pixelscope_enterprise/**       + internal model/server/auth/storage
  + internal full packaging           + SUB-owned tests/configuration
```

Core must **not** import either extension. Reference and Enterprise are peer
consumers of MAIN APIs: SUB must not import `pixelscope_iqa_reference` internals
as production dependencies.

The completed Slice 8 snapshot is
`19cf5d395fb86c62d55a28355e3beb147f5dd8bf` (PR #133).
Use an **explicit, verified MAIN commit SHA**, not a moving branch, for each SUB
integration. A later MAIN docs-only closeout commit does not change the Slice 8
snapshot; pin any newer MAIN SHA explicitly if selected.

## Repository layout and permanent ownership

The following is a *logical example* when SUB consumes/merges a full MAIN tree.
It is not a demand that internal repository remotes use a particular Git layout.

```text
SUB/
  src/
    pixelscope/**                  MAIN-owned inherited Core/public contract
    pixelscope_iqa_reference/**    MAIN-owned optional public example
    pixelscope_enterprise/**       SUB-owned real Enterprise extension
  tests/
    unit/**, ui/**, conformance/**, iqa_reference/**
                                   MAIN-owned inherited public regression
    enterprise/**                 SUB-owned unit/UI/integration/conformance/smoke
  docs/
    IQA_HANDOFF.md                 MAIN-owned public handoff
    IQA_ENTERPRISE_SUB_GUIDE.md    MAIN-owned public implementation guide
    enterprise/**                 SUB-owned internal architecture and operations
  enterprise/**                   SUB-owned launcher, packaging, deployment/config
```

Only these paths are reserved for SUB:

```text
src/pixelscope_enterprise/**
tests/enterprise/**
docs/enterprise/**
enterprise/**
```

All other inherited MAIN files are upstream-owned. No permanent SUB patch should
modify MAIN-owned files; a missing generic host/contract capability becomes a
company-neutral MAIN request, implemented/tested publicly and consumed via a newer
MAIN SHA. MAIN never consumes internal source, URLs, credentials, proprietary
schema, storage topology or configuration.

## Expected SUB execution / implementation sequence

1. **Bootstrap against an exact MAIN SHA.** Verify provenance, establish SUB-only
   paths, register a minimal Enterprise extension with public
   `WindowContribution` / optional runtime/settings contribution hooks.
   Confirm Core can launch without it and Enterprise can launch/shut down with
   no edits to MAIN-owned files.
2. **Establish Enterprise shell with a synthetic provider.** Own the IQA-specific
   dock, commands, settings UI and controller in SUB. Exercise public execution
   and result-access protocols without contacting an internal server.
3. **Implement real provider/adapters in SUB.** Add model/server execution,
   authentication, shared-storage staging/cleanup, request/result schemas,
   source resolver and normalized public result adaptation behind the Qt-free
   public ports. Respect same-instance concurrency, failure sanitization and
   ambiguous-submit rules.
4. **Recover and migrate relevant P5 behavioral tests.** Use the audit below
   before writing new tests. Preserve valuable invariants/fixtures, but adapt
   imports, ownership, fakes and assertions to the new Enterprise architecture.
   Do not reintroduce deleted P5 production classes into MAIN.
5. **Build the internal Full product.** Validate installation, explicit Enterprise
   composition, offline opening of materialized results, real integration smoke
   where authorized, clean Qt/native teardown and source provenance.
6. **Prove repeatable MAIN upgrades.** Fetch/merge another approved MAIN SHA,
   run public + Enterprise regressions, and document any upstream-first generic
   contract changes. No recurring downstream merge edits to MAIN-owned paths.

These are **new downstream work items** after Issue #121, not unfinished MAIN
slices or an implied Slice 9. The SUB orchestrator should own prioritization,
slice breakdown, PRs, internal review, and acceptance evidence.

## Tests: where they live and how to run them

SUB tests are **not automatically populated by Issue #121**. Whether a private
SUB repository has existing tests must be verified *inside SUB*; this public
document does not claim to have inspected the private tree.

In a SUB checkout that includes the MAIN test tree under `tests/` and retains
`pyproject.toml`'s `testpaths = ["tests"]`, these commands apply:

```powershell
# Enterprise only (once tests/enterprise exists)
.\.venv\Scripts\python.exe -m pytest -q tests/enterprise

# MAIN public boundary plus Enterprise (integration/contract smoke)
.\.venv\Scripts\python.exe -m pytest -q tests/conformance tests/enterprise

# All tests discoverable in this SUB checkout: inherited MAIN + SUB
.\.venv\Scripts\python.exe -m pytest -q
```

`pytest -q` controls output verbosity; **test discovery depends on the checkout,
test paths, imports, installed dependencies and pytest configuration**. If SUB uses
a separate checkout/dependency arrangement, it must explicitly include both
inherited/public and Enterprise test suites in its own orchestration; merely
depending on a MAIN wheel does not cause MAIN repository tests to be collected.
The observed owner-local Slice 8 MAIN baseline was **1344 passed**, not a fixed
required number for every later SUB environment.

Keep deterministic Enterprise unit/conformance and synthetic/UI tests in the
normal suite. Separate live server, GPU, credentials, external-storage,
installer/deployment and long-running smoke behind explicit internal markers
or dedicated commands; do not make ordinary `pytest -q` depend on live services.
Exercise lifecycle-sensitive Qt tests under the existing Issue #81 constraints:
normal cyclic GC, no arbitrary sleeps/timeouts, no suppressed native failures.

At minimum SUB should test:
- Enterprise extension load/composition/settings ownership and clean shutdown;
- public protocol/same-instance concurrency/error/partial/missing semantics;
- submit/cancel/status/result/materialize/open/source-resolution flows;
- staging, authorization, real-result adapters and local reopen via internal fakes;
- UI stale callback and native worker/QObject lifecycle behavior;
- Internal Full packaging and exact MAIN/SUB/contract/config revision provenance.

## Where the 43 retired P5 test modules are archived

**They are not copied into a new archive directory or into SUB.** They were
deleted from the latest MAIN working tree as part of Slice 8, and remain readable
at the immutable **merged Slice 7 Git snapshot**:

```text
29561bdb70e722380a8041212d991ae21b72c6be
```

Earlier mixed implementation reference:
`037fda2dc3e79475b5ba1841e8308bbbe5d0cd07`.
Slice 8 merged output:
`19cf5d395fb86c62d55a28355e3beb147f5dd8bf`.

Useful read-only commands from a repository containing MAIN Git history:

```powershell
# List deletion/rename classification between Slice 7 and Slice 8
git diff --name-status 29561bdb70e722380a8041212d991ae21b72c6be 19cf5d395fb86c62d55a28355e3beb147f5dd8bf -- tests/

# Inspect an original test without modifying current source
git show 29561bdb70e722380a8041212d991ae21b72c6be:tests/unit/test_p5c_submission.py

# Compare only the historical file's content or copy it to a temporary
# work area for review; do not restore retired imports into public MAIN.
```

Files removed between those exact snapshots (**19 UI + 24 unit = 43 test files**):

### Legacy P5 / Remote-IQA UI tests (19)

```text
tests/ui/test_beta_pass2_iqa_stress.py
tests/ui/test_iqa_public_fixture_profiles.py
tests/ui/test_issue121_iqa_composition_seam.py
tests/ui/test_p5b_iqa_workspace.py
tests/ui/test_p5c_authority_closeout.py
tests/ui/test_p5c_debug_replay_ui.py
tests/ui/test_p5c_remote_iqa.py
tests/ui/test_p5c_result_mapping.py
tests/ui/test_p5c_result_retry.py
tests/ui/test_p5c_setup_presentation.py
tests/ui/test_p5c_submission_lifecycle.py
tests/ui/test_p5d_alias_spatial_binding.py
tests/ui/test_p5d_review_closeout.py
tests/ui/test_p5d_stale_inspection.py
tests/ui/test_p5d_viewer_linked_inspection.py
tests/ui/test_p5e_file_menu_order.py
tests/ui/test_p5e_historical_results.py
tests/ui/test_p5e_review_regressions.py
tests/ui/test_p5f_worker_isolation.py
```

### Legacy P5 / Remote-IQA unit tests (24)

```text
tests/unit/test_iqa_current_pair_contract.py
tests/unit/test_iqa_explorer.py
tests/unit/test_p5c_debug_replay.py
tests/unit/test_p5c_localhost_http.py
tests/unit/test_p5c_partial_v2.py
tests/unit/test_p5c_request_debug.py
tests/unit/test_p5c_storage_hardening.py
tests/unit/test_p5c_submission.py
tests/unit/test_p5c_submission_cancellation.py
tests/unit/test_p5d_review_closeout_unit.py
tests/unit/test_p5d_scene_inspection.py
tests/unit/test_p5d_source_locator_identity.py
tests/unit/test_p5e_iqa_history.py
tests/unit/test_p5f_compatibility_probe.py
tests/unit/test_p5f_diagnostics.py
tests/unit/test_p5f_transport_pool.py
tests/unit/test_p5g_iqa_preflight.py
tests/unit/test_remote_iqa_diagnostics.py
tests/unit/test_remote_iqa_storage_diagnostics.py
tests/unit/test_remote_iqa_transport_policy.py
tests/unit/test_remote_iqa_v1.py
tests/unit/test_remote_iqa_v2.py
tests/unit/test_remote_iqa_v2_limits.py
tests/unit/test_remote_iqa_v2_review_regressions.py
```

These file counts are Git path counts, **not** pytest collected-case counts.
A single module may contain many parametrized tests, so the reduction from
the older full suite to 1344 current MAIN cases cannot be attributed one-for-one
to a number of deleted files.

### Migration decision per old test

| Historical test intent | New owner/action |
| --- | --- |
| Generic Base/Viewer/RAW/YUV/Settings/lifecycle | Keep/rely on surviving MAIN tests; do not fork into SUB |
| Public job/result contracts and synthetic semantics | Use maintained MAIN conformance/fixture/reference tests |
| Real execution/HTTP, authentication, storage/staging, schema/result adaptation | Port reusable behavior to `tests/enterprise/**` alongside the real SUB implementation |
| Old P5 widget wiring, concrete class/transport imports, unsupported v1/v2 compatibility | Historical reference only unless SUB explicitly adopts that behavior |

For each candidate, record its original path, invariant, new owner, disposition
(`reuse` / `adapt` / `replace` / `archive-only`) and new test path in an
**internal SUB migration inventory**. A deleted MAIN test is not automatically an
Enterprise acceptance test; and an archive-only decision must not silently discard
a still-required product behavior.

## Contract and handoff closure

MAIN provides public host APIs, synthetic fixtures, conformance tests and the
Core/Reference packaging definitions; internal real IQA functionality is not an
Issue #121 MAIN deliverable. MAIN's Slice 8 source retirement and public boundary
are merged, and the owner reported 1344 passing public tests with hosted validation
green on PR #133. **Core/Reference packaged executable smoke is not independently
attested by this record**; do not relabel unit/package-contract tests as real
release smoke. The SUB agent must also produce its own Full-product evidence.

Document every internal release's exact `MAIN_SHA`, `SUB_SHA_or_revision`,
`IQA_PUBLIC_CONTRACT_REVISION` and `internal_configuration_revision`.
No Enterprise implementation or secret is to be committed to this public guide.
