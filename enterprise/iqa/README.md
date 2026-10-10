# IQA public-safe handoff: ownership and immutable transfer protocol

Status: **pre-approval tooling/schema**, Issue #156 H1 (U3 + U11). This folder
belongs to the temporary, PUBLIC-SAFE **handoff** branch. Never merge these files
into PUBLIC `main` or put company/private values here.

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

- **(a) Default: manifest/path-delta**. A subsequent external manifest records
  the previous approved SHA and all updates/deletions explicitly. A new SHA
  need not be a descendant, but collisions are checked against the previous
  manifest and operator-approved. Preserves SUB sibling ownership.
- **(b) Optional: history-preserving merge**. A later approved handoff commit
  must descend from the previous approved commit **and** SUB must share real Git
  ancestry (not a prior `git restore` copy). Review the resulting merge diff and
  deletion scope. A tag alone does not create shared ancestry. If ancestry
  policy is broken, revert to (a) rather than rewriting approved history.

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

For updates, also pass
`--previous-manifest <PREVIOUS_APPROVED_MANIFEST_JSON>` to **both**
commands. The tool rejects paths outside IQA leaves, Git symlinks,
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
& $py -m pytest -q tests/enterprise/iqa/test_handoff_manifest.py
& $py -m ruff check enterprise/iqa/handoff_manifest.py tests/enterprise/iqa/test_handoff_manifest.py
& $py -m ruff format --check enterprise/iqa/handoff_manifest.py tests/enterprise/iqa/test_handoff_manifest.py
```

Pending #159 Slice B may add additional IQA tests/docs at their old
flat locations; normalize them into these owned leaves **before H1 approval**.
