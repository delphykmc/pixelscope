# UX-3E E2 — SHA-pinned post-import verification and PRIVATE SUB release gate

Status: **PUBLIC-SAFE development protocol; NO approved release, PRIVATE SUB
import, deployment or production package is certified by this document**.
Tracking: #168, #156 (U2/U3/U9/U11), #140 (portable result contract).

## Ownership and upstream reconciliation

- Temporary public-safe **Handoff** is the sole owner of
  `src/pixelscope_enterprise/iqa/**`, `tests/enterprise/iqa/**`,
  `docs/enterprise/iqa/**`, `enterprise/iqa/**` and the minimal
  `src/pixelscope_enterprise/__init__.py`. Never merge these into PUBLIC
  `main`; preserve PRIVATE SUB sibling trees.
- MAIN generic caller-selected packaging descriptor was merged in
  PUBLIC PR #167 (`4a85285c49bb97d90f92fdb6edfc81702242a269`).
  The original E1/E2A Handoff history predated this integration, so MAIN
  ancestry could **not** be assumed. The E2B *candidate branch* first
  incorporated PUBLIC `main@dca0464b66934b62aa759f2e38e0b79b40de353b`
  via genuine two-parent merge `37478a43787fd1ec92413ad8ec2d8515c5e43767`.
  Then PUBLIC #174 fixed the Issue #121/U8 test allowlist in `main` at
  `3bef0880add2019d62f783d717eb1be518144e19`; E2B consumed this
  exact newer MAIN SHA through second two-parent merge
  `44adc97adeba50357702ea3cf5cf8295a6c19a8a`.
  See [E2B ancestry acceptance](IQA_UX3E_E2B_MAIN_SYNC.md).
  **Do not squash the E2B PR**: only a reviewed ordinary Git Merge commit
  into Handoff preserves MAIN as a real ancestor of the final handoff SHA.
  Verify both ancestry and exact combined inventory after that merge before
  generating an approved manifest. Never force-push/rebase an approved SHA.
  This candidate is not yet a protected/approved handoff release.
- PRIVATE SUB owns its real Full launcher, descriptor, PyInstaller spec,
  dependencies, smoke target, service/auth and installer signing outside
  replaceable `enterprise/iqa/**` leaves.
- UX-3D real portable result loader/writer remains **blocked by #140** and
  cannot be substituted with synthetic IQA reports.

## Acceptance sequence (all gates mandatory)

1. **Prepare evidence, not placeholder PASS values.** Independently review
   security/privacy and actual owner Windows 3.10/PySide6 focused tests.
   Document any NOT RUN hardware DPI/dual-monitor checks; distinguish
   model/Qt tests from package smoke. Do not copy private data to public docs.
2. **Freeze one final Handoff SHA** from the approved commit after E2 merges.
   Verify chosen `main_base_sha` is really an ancestor and the public
   `IQA_PUBLIC_CONTRACT_REVISION` agrees. For subsequent releases verify
   the prior approved Handoff SHA is an ancestor. Create an annotated
   `handoff/iqa/vN` tag protected by actual repository ruleset/retention;
   this PR does not create such a tag.
3. **Publish a separate externally retained Manifest** with actual reviewer,
   time, validation evidence and SHA-256 integrity. The manifest cannot
   embed its own final SHA inside the Git commit it attests; do not commit a
   fake approved JSON into the public Handoff tree. Protect/authenticate the
   external manifest artifact independently.
4. PRIVATE SUB fetches the **exact approved Git objects**, validates tag,
   ancestry, manifest hashes/modes/path scope and previews every file
   operation; abort on private path collision/symlinks/unexpected deletions.
   Take a private checkpoint, then explicitly apply only the approved
   path-delta. Do NOT `git restore` whole reserved directories.
5. **Run the new read-only post-import verification** against exactly the
   protected approved JSON. It requires **no remaining approved file
   operations** and rejects changed/missing managed files or unapplied
   removals. It checks the approved Handoff snapshot, not the contents or
   safety of any proprietary PRIVATE SUB sibling. Verify protected sibling
   checksums separately from the private pre-import checkpoint and review
   the diff; do not infer sibling preservation solely from the new verifier.
6. PRIVATE SUB uses the PUBLIC **#167** `--target-descriptor` release flow
   on an authorized Windows host, including packaging, artifact validation,
   portable/installer smokes, license inventory, private dependency/SBOM,
   version/provenance and binary/signing review. A passing synthetic
   manifest/CI is not a Full package acceptance.
7. Record approved Handoff SHA, MAIN SHA, manifest digest, external tag,
   complete imported diff/deletions, protected sibling comparison, approved
   Full target descriptor and smoke results in PRIVATE SUB. Only then call
   the transfer/release complete. Any subsequent Handoff updates require a
   new reviewed descendant commit, protected tag and external manifest.

## Actual command sequence (illustrative; paths/SHA/times are placeholders)

**Generation** requires approved frozen SHA, protected tag and genuine owner
validation evidence. After approval in a checkout with required Git objects:

```powershell
& $py enterprise/iqa/handoff_manifest.py generate `
  --repo . --main-base-sha <ACTUAL_MAIN_ANCESTOR_SHA> `
  --handoff-sha <ACTUAL_APPROVED_HANDOFF_SHA> `
  --tag handoff/iqa/v1 --reviewed-by <APPROVED_PUBLIC_REVIEW_ID> `
  --approved-at <ACTUAL_ISO_8601_APPROVAL_TIME> `
  --evidence <EXTERNAL_ACTUAL_TEST_EVIDENCE_JSON> `
  --output <EXTERNAL_PROTECTED_MANIFEST_JSON>
```

On authorized PRIVATE SUB, first dry-run then review and apply:

```powershell
& $py enterprise/iqa/handoff_manifest.py import `
  --repo <FETCHED_PUBLIC_GIT_OBJECTS> --destination <PRIVATE_SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON>

# Only after separate owner approval and a PRIVATE SUB checkpoint:
& $py enterprise/iqa/handoff_manifest.py import `
  --repo <FETCHED_PUBLIC_GIT_OBJECTS> --destination <PRIVATE_SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON> --apply

# Read-only post-import reconciliation; no writes, no approval substitution:
& $py enterprise/iqa/handoff_manifest.py verify `
  --repo <FETCHED_PUBLIC_GIT_OBJECTS> --destination <PRIVATE_SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON>
```

For an **incremental** update, pass
`--previous-manifest <PREVIOUS_APPROVED_MANIFEST_JSON>` to **import and
verify**. The verifier refuses a partially applied approved snapshot and
prints the digest of the **manifest file bytes** for the private approval
record. That digest is *not* a signature or an authentication mechanism.

Use the existing #167 instructions in
`docs/iqa/IQA_U2_TARGET_DESCRIPTOR.md` for the eight executable build /
artifact validator / packaged smoke / portable build and smoke / Inno build
and smoke / bundle validation commands. Do not generate or commit a real
internal descriptor into the public Handoff repo.

## Fast E2 contract regressions (no private data)

```powershell
$env:PYTHONPATH = "src"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_handoff_manifest.py
```

One optional real-Git smoke per release/tooling change, separate process:

```powershell
$env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION = "1"
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_handoff_manifest_git.py
Remove-Item Env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION -ErrorAction SilentlyContinue
```

New regression cases: no false PASS before files are imported, altered
managed file refusal without writes, missing/unapplied deletion refusal,
completed full-snapshot match, incremental previous-manifest requirement,
and unrelated SUB sibling bytes preserved in synthetic scenarios. Existing
Git/tag/path/ancestry/symlink/sha256 checks are reused, not duplicated.

**Development merge criteria:** owner Windows synthetic import/verify
tests PASS and independent review PASS. Ordinary Enterprise-only slices such
as E1/E2A may use Handoff-only squash merges; **E2B is an exception and MUST
use a regular Git merge commit (never squash or rebase)** so the approved
PUBLIC MAIN SHA remains an actual Handoff ancestor. After E2B, verify Handoff
descends from both PUBLIC MAIN `3bef0880add2019d62f783d717eb1be518144e19`
and pre-sync Handoff `c27abc9169917c8b49f4c0b48db2d49fc79853a0`.

**Release approval remains BLOCKED** until the protected tag and authenticated
external manifest, PRIVATE SUB checkpoint/sibling comparison/import/verify,
U2/U9 real Full packaging smoke and security owner authorization are complete.
Mark any unperformed step explicitly NOT RUN.
