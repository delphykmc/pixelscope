# IQA public-safe handoff: ownership and immutable transfer protocol

Status: **pre-approval tooling/schema**, Issue #156 H1 (U3 + U11). This folder
belongs to the temporary, PUBLIC-SAFE **handoff** branch. Never merge these files
into PUBLIC `main` or put company/private values here.

## U7 owner/local test matrix

See [IQA U7 Validation Matrix](../../docs/enterprise/iqa/IQA_U7_VALIDATION_MATRIX.md)
for separate-process numeric versus native Qt acceptance commands, opt-in
real-host and Git tests, and existing GitHub CI classifier behavior. A merged
Handoff SHA is **not** an approved/private import; only actual test evidence
from the exact reviewed SHA may appear in an approved external manifest.

## Allowed IQA-owned leaves

Only files under these leaves may be transferred into PRIVATE SUB:

```text
src/pixelscope_enterprise/iqa/**
tests/enterprise/iqa/**
docs/enterprise/iqa/**
enterprise/iqa/**
```

The single shared `src/pixelscope_enterprise/__init__.py` is an optional,
minimal namespace initializer: transfer it only after verifying it does not
replace or modify a SUB-owned initializer. Paths like
`tests/enterprise/other_team/**` and `enterprise/other_feature/**`
are **never** import targets or deletion candidates. PUBLIC MAIN has no
responsibility for these reserved roots.

## The SHA/manifest chicken-and-egg rule

A manifest committed *inside* the handoff commit cannot embed its own
`handoff_sha` (a self-referential Git hash). Keep the **schema, policy and
generator** under `enterprise/iqa/**`; generate the **concrete approved
manifest after the final commit SHA is frozen**, and publish that JSON as an
immutable externally retained release/approval artifact paired with the
protected annotated tag `handoff/iqa/vN`. The externally published JSON is
machine-readable and must validate against
`handoff_manifest.schema.json`.

The manifest must state the exact merged PUBLIC `main_base_sha`,
`IQA_PUBLIC_CONTRACT_REVISION`, the approved 40-hex `handoff_sha`, prior
approved SHA (if any), human `reviewed_by` and `approved_at`, explicit
add/update paths (Git blob SHA, SHA-256, mode), explicit removed paths with
previous hashes, and actual per-process validation evidence. The approval
record/manifest should itself be integrity-protected and retained outside the
mutable development branch (for example in a protected release artifact).
No private reviewer identities, file paths, infrastructure or passwords are
committed to the temporary PUBLIC branch.

## Review, approval, versioning

1. Review code, privacy, imports, build commands and native Windows Qt tests.
   `merged-to-handoff` is **not** `approved-for-SUB`.
2. Freeze an exact reviewed handoff commit. Create an annotated,
   protected/immutable `handoff/iqa/vN` tag that resolves to that SHA.
   Merely creating an unprotected tag is *not* immutability enforcement;
   repository admin must configure tag protection/ruleset and retention.
3. Create the external manifest **after** the SHA is known. Validate every
   listed path/hash/mode against the frozen Git tree and actual test evidence.
   Publish and preserve the manifest with the tag/approval record. Never force
   push or delete this approved tag/ref or rewrite approved commits.
4. In PRIVATE SUB, fetch the approved SHA/tag and verify Git ancestry,
   explicit `main_base_sha` provenance and the frozen manifest's integrity.
   Preview a file-by-file diff before importing. Verify all input blobs/sha256.
   Check for collisions against SUB-owned files and obtain owner approval.
5. Apply **only allowlisted per-file** add/update entries and **explicit**
   deletions listed with previous content hashes. Verify expected old content
   before every overwrite or removal; if it diverges, abort for conflict
   resolution. Do not infer deletion from files missing in a directory or
   from handoff branch HEAD. Verify resulting hashes/tests after import.
6. Record the approved handoff SHA, manifest digest, tag, import diff and
   downstream validation in PRIVATE SUB. Only the temporary *development
   branch* may later be cleaned up after a verified transfer.

**PROHIBITED:** `git restore --source=<SHA> -- src/pixelscope_enterprise
tests/enterprise docs/enterprise enterprise`, because restoring whole reserved
roots can wipe unrelated private sibling files.

## Future updates and transfer modes

- **Mandatory PUBLIC approval lineage:** every next approved handoff SHA must
  descend from the previous approved SHA, regardless of PRIVATE SUB import
  mode. Retain protected approval tags; neither mode permits rewriting
  approved public history.
- **(a) Default: manifest/path-delta**. A subsequent external manifest records
  the previous approved SHA and all updates/deletions explicitly. Collisions
  are checked against the previous manifest and operator-approved; unrelated
  SUB siblings remain outside the import scope.
- **(b) Optional: history-preserving merge**. PRIVATE SUB must have actual
  ancestry for an approved handoff SHA, not just copied files. After the
  initial verified path-delta import, a PRIVATE SUB-owned *ancestry bridge*
  commit can retain the approved handoff commit as an additional parent,
  but must be reviewed to ensure its full tree equals the already verified
  PRIVATE SUB tree. Such a bridge does not authorize wholesale overwrites.
  Before later merges, independently inspect the three-way merge diff and
  all sibling/deletion collisions. If PRIVATE SUB merge ancestry is missing,
  fall back to (a) without rewriting the approved PUBLIC handoff history.

## Tooling / dry-run-first procedure

The stdlib-only `handoff_manifest.py` uses **only immutable Git blobs** to
build a candidate manifest; it does not determine whether security approval
was actually granted. After independent review, approved SHA/tag freeze,
real Windows validation, and review of the evidence JSON array:

```powershell
& $py enterprise/iqa/handoff_manifest.py generate `
  --repo . --main-base-sha <MERGED_MAIN_SHA> --handoff-sha <FROZEN_HANDOFF_SHA> `
  --tag handoff/iqa/v1 --reviewed-by <PUBLIC_SAFE_REVIEW_ID> `
  --approved-at 2026-10-10T00:00:00+00:00 `
  --evidence <ACTUAL_TEST_EVIDENCE_JSON> --output <EXTERNAL_MANIFEST_JSON>
```

The timestamp is an **example**, not an approval claim. Record actual test
commands, OS, Python/Qt and outcomes (do not fabricate PASS entries).
Validate the output with `handoff_manifest.schema.json`. Hash/sign/publish
the resulting JSON as an **external protected** approval artifact paired
with the protected tag; do not commit it into the SHA that it authenticates.

PRIVATE SUB imports after retrieving the **same approved Git objects and
the externally authenticated JSON**, not from mutable handoff HEAD:

```powershell
& $py enterprise/iqa/handoff_manifest.py import `
  --repo <REPO_WITH_FETCHED_HANDOFF_TAG> --destination <SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON>
# Review every printed path and operation. ONLY after approval:
& $py enterprise/iqa/handoff_manifest.py import `
  --repo <REPO_WITH_FETCHED_HANDOFF_TAG> --destination <SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON> --apply
```

**New UX-3E E2 post-import audit:** after approved `--apply`, use the
read-only `verify` command with the same protected manifest and exact Git
objects. It fails closed when any approved file is absent/altered or an
explicit deletion was not performed, and prints a digest of the externally
retained manifest for the private evidence record:

```powershell
& $py enterprise/iqa/handoff_manifest.py verify `
  --repo <REPO_WITH_FETCHED_HANDOFF_TAG> --destination <SUB_CHECKOUT> `
  --manifest <APPROVED_MANIFEST_JSON>
```

For incremental transfers pass the previous approved manifest to the
`verify` command as well. This is a **post-import content reconciliation**,
not a cryptographic approval signature, protected-tag configuration, a
PRIVATE SUB sibling-diff verifier or any Full package certification. For
the E2 security and release gates see
[`IQA_UX3E_E2_TRANSFER_ACCEPTANCE.md`](../../docs/enterprise/iqa/IQA_UX3E_E2_TRANSFER_ACCEPTANCE.md).

For updates, also pass
`--previous-manifest <PREVIOUS_APPROVED_MANIFEST_JSON>` to **both**
`import` commands. The tool rejects paths outside IQA leaves, Git symlinks,
untracked-content collisions, altered files that do not match previous
SHA-256, unlisted/extra files in the approved IQA tree, missing approval
tags, and missing/mismatched previous snapshots. All preflight checks
complete before the first write; the apply phase is **not** an atomic
repository transaction, so take a private checkpoint and inspect `git diff`
before committing. No code-level signature verifier or Git ruleset
installer is provided: protection and manifest authentication are
an explicit external owner/release responsibility.

Owner-local validation:
```powershell
& $py -m pytest -q --durations=5 tests/enterprise/iqa/test_handoff_manifest.py
& $py -m ruff check enterprise/iqa/handoff_manifest.py tests/enterprise/iqa/test_handoff_manifest.py
& $py -m ruff format --check enterprise/iqa/handoff_manifest.py tests/enterprise/iqa/test_handoff_manifest.py
```

### Validation cost policy

The standard **five fast security/contract tests** in
`tests/enterprise/iqa/test_handoff_manifest.py` use an in-memory synthetic
Git model. They still exercise the production generator/import planner,
snapshot hash rejection, explicit update/deletion, sibling preservation,
path traversal, wrong tag/non-ancestry, and symlink checks. They no longer
invoke external Git for each test. The tests are not a substitute for
a real Git integration check.

A **separate opt-in real Git smoke**
`tests/enterprise/iqa/test_handoff_manifest_git.py` creates one synthetic
repository, checks commit/tag/tree and binary-safe `git cat-file --batch`,
and applies a sandbox import. It is skipped by default, including when
the general full suite discovers it. Run it **once before approval or
when changing the Git protocol/release tooling**, not for ordinary GUI/IQA
development:

```powershell
$env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION = "1"
& $py -m pytest -q --durations=5 tests/enterprise/iqa/test_handoff_manifest_git.py
Remove-Item Env:PIXELSCOPE_RUN_HANDOFF_GIT_INTEGRATION -ErrorAction SilentlyContinue
```

A real PRIVATE SUB import still requires the verified SHA/tag, protected
external manifest, collision review, dry run and post-import validation.
A successful synthetic Git smoke does **not** grant security approval.
The importer itself continues to batch Git blob reads to avoid spawning
one `git cat-file` subprocess per file.

Pending #159 Slice B may add additional IQA tests/docs at their old
flat locations; normalize them into these owned leaves **before H1 approval**.
