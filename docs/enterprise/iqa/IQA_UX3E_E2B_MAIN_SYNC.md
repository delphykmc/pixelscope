# UX-3E E2B — Real PUBLIC MAIN ancestry integration into Enterprise Handoff

Tracking: #168, #156 U1/U2/U8/U9/U11, #140.
**Status: development candidate only; NOT an approved Handoff SHA/tag, PRIVATE SUB import, Full binary or release.**
**Target branch: `handoff/enterprise-iqa-window`, never PUBLIC `main`.**

## Exact pre-integration objects (2026-10-10)

| Identity | Exact Git SHA |
| --- | --- |
| Frozen E2A Handoff development parent (#172) | `c27abc9169917c8b49f4c0b48db2d49fc79853a0` |
| PUBLIC MAIN consumed (contains #164 U8, #167 U2 and #156 U9 docs) | `dca0464b66934b62aa759f2e38e0b79b40de353b` |
| Common pre-integration ancestor | `95b7845e731302934e21033a0ee09ef08947495a` |
| **Actual two-parent E2B merge candidate** | `37478a43787fd1ec92413ad8ec2d8515c5e43767` |
| Combined candidate Git tree | `eb1a6eb883a0fe143ef465d87ab655c3b9f27627` |

The candidate commit has **first parent Handoff**, **second parent PUBLIC MAIN**.
No rebasing/force-pushing or approval tag changes were performed. Its tree
was assembled exclusively from the Handoff tree plus the latest exact blobs
for **23 changed MAIN-owned paths**. Review against the common ancestor
found **55 Handoff-only changed Enterprise paths**, **zero overlapping
changed paths** and **no changed MAIN-owned paths inside Enterprise roots**.
The final tree was compared at path, Git mode and blob SHA for every file:
**652/652 blobs exactly match the union**, with no missing/extra paths.

GitHub compare checks subsequently confirmed that both frozen parents are
actual ancestors of `37478a43` (ahead, behind 0), not just a string in a
release note. The combined candidate includes the existing U2 packaging
descriptor and new U9 release docs, but no PRIVATE SUB source/spec.

## CRITICAL merge-method exception

**Do NOT squash or rebase the E2B PR into Handoff.** Squashing a branch
containing a two-parent merge discards the extra MAIN parent and the exact
MAIN SHA would NOT be an ancestor of the resulting Handoff head. That would
violate the #156 U11 provenance condition and cause
`enterprise/iqa/handoff_manifest.py generate/import/verify` to reject
`main_base_sha=dca0464b...` as not being an ancestor.

After independent review and owner acceptance, merge the E2B PR using
**GitHub Merge Commit** (`merge_method=merge`), not the normal E1/E2A
`squash` default. The resulting Handoff commit must descend from both
`c27abc91` and `dca0464b`. Both historical HEAD SHAs remain reachable.
Do not merge Handoff back into MAIN. A later separate change can use squash
for ordinary Enterprise-only patches because MAIN is already an ancestor
of the Handoff parent; this exception is limited to the upstream sync.

## Owner Windows 3.10 evidence gates

The following are public-safe tests. They do **not** build any real PRIVATE
SUB Full descriptor or installer; reuse the U2/U9 procedure after approval.

```powershell
git fetch origin
git switch feat/168-enterprise-iqa-ux3e-e2b-main-ancestry
git pull --ff-only
git status --short
git rev-parse HEAD

$py = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$env:PYTHONPATH = "src"
$env:PIXELSCOPE_PUBLIC_MAIN_SHA = "dca0464b66934b62aa759f2e38e0b79b40de353b"
$env:PIXELSCOPE_HANDOFF_PRE_SYNC_SHA = "c27abc9169917c8b49f4c0b48db2d49fc79853a0"
$env:PIXELSCOPE_HANDOFF_MAIN_MERGE_SHA = "37478a43787fd1ec92413ad8ec2d8515c5e43767"
$env:PIXELSCOPE_RUN_IQA_MAIN_SYNC = "1"

# Independent process: hard Git ancestry and all MAIN/Handoff file modes/blobs.
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_iqa_e2b_main_ancestry.py
if ($LASTEXITCODE -ne 0) { throw "E2B Git ancestry/inventory acceptance failed" }

# PUBLIC MAIN conformance and release plumbing (no Full native build).
& $py -m pytest -q -W error::DeprecationWarning `
  tests/conformance/test_iqa_provider_handoff.py `
  tests/conformance/test_iqa_provider_runner.py `
  tests/unit/test_release_target_descriptor.py `
  tests/unit/test_ci_test_groups.py
if ($LASTEXITCODE -ne 0) { throw "PUBLIC conformance/release integration failed" }

# MAIN ownership guard explicitly inspects the pinned MAIN *tree* even in a
# checkout containing tracked Handoff Enterprise files.
& $py -m pytest -q -W error::DeprecationWarning `
  tests/unit/test_issue121_iqa_reference_architecture.py
if ($LASTEXITCODE -ne 0) { throw "MAIN ownership/import-direction gate failed" }

# Enterprise manifest + E2A import/verify (no physical PRIVATE SUB import).
& $py -m pytest -q -W error::DeprecationWarning `
  tests/enterprise/iqa/test_handoff_manifest.py
if ($LASTEXITCODE -ne 0) { throw "Handoff manifest contract gate failed" }

Remove-Item Env:PIXELSCOPE_RUN_IQA_MAIN_SYNC -ErrorAction SilentlyContinue
Remove-Item Env:PIXELSCOPE_HANDOFF_PRE_SYNC_SHA -ErrorAction SilentlyContinue
Remove-Item Env:PIXELSCOPE_HANDOFF_MAIN_MERGE_SHA -ErrorAction SilentlyContinue
Remove-Item Env:PIXELSCOPE_PUBLIC_MAIN_SHA -ErrorAction SilentlyContinue
```

If project tests or PyInstaller release require dependencies not present,
install the established pinned development/release requirements in the
owner environment; do not manufacture PRIVATE SUB inputs. Run GUI/native
Qt acceptance **in separate processes** using the U7 / UX-3E E1 matrix
and record any native crash/teardown. The opt-in real-Git Manifest test
should be run once separately before a protected approval release.

### Test interpretation

- The E2B ancestry test uses Git `rev-list` and `merge-base --is-ancestor`
  to reject an E2B squash masquerading as a merge, then compares
  **every** MAIN-owned mode/blob to the exact frozen MAIN commit. It
  separately verifies all previously reviewed Handoff Enterprise blobs
  remain unchanged; new IQA-only tests/docs are permitted.
- `PIXELSCOPE_PUBLIC_MAIN_SHA` is required for the #156 U1 ownership
  guard in a Handoff checkout, and must point to a real merged PUBLIC
  ancestor rather than Handoff HEAD.
- The Windows symlink test may SKIP without developer-mode privileges.
  Record that SKIP; do not claim it demonstrates symlink rejection.
- A PASS on this candidate is **not** a PASS for later Handoff PR heads
  without recomputing the exact-head CI/test evidence.
- STATIC/GitHub CI is a distinct check: Ruff/format/mypy plus
  change-driven Windows release tests as selected by CI. New
  Enterprise native suites remain owner-local by policy.

## Security and release handoff after E2B

1. Independently review candidate E2B changes and native/contract tests;
   merge by **non-squash** `merge` into Handoff and verify ancestry again.
2. Choose and freeze the final **post-merge Handoff** SHA; create a truly
   protected annotated `handoff/iqa/vN` tag only after security owner
   approval. This development merge is **NOT approval**. The public
   `main_base_sha` for that frozen commit can then use the verified
   `dca0464b...` pin (or a later verified ancestor after another sync).
3. Generate the actual external approved JSON using
   `enterprise/iqa/handoff_manifest.py generate`, with real validation
   evidence, reviewer identity, time and contract revision. Authenticate/
   retain it outside this repository; no self-referential SHA/placeholder.
4. In authorized PRIVATE SUB, use **manifest/path-delta import** by
   default, independently review possible sibling collisions/deletions,
   checkpoint private files, apply only allowlisted entries, and run E2A's
   **read-only `verify`**. This does not authenticate the artifact.
5. PRIVATE SUB performs U9 descriptor/spec/dependency/SBOM and U2 Windows
   Full PyInstaller, validator, packaged/portable/Inno smokes, approvals.
   The public checkout neither ships nor executes those real private files.
6. #140 portable IQA Result Open/Save remains disabled without an approved
   real format and verified reader/writer. Parent #168/#153/#156 remain open
   until full PRIVATE SUB release acceptance, not merely Handoff merges.

See `docs/enterprise/iqa/IQA_UX3E_E2_TRANSFER_ACCEPTANCE.md` for the
external Manifest/import/approval sequence, and
`docs/iqa/IQA_U9_SUB_PACKAGING_GUIDE.md` for PRIVATE SUB U9 build gates.
