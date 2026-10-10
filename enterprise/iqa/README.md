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

Do not perform a bulk SUB import before the manifest producer/verifier,
collision-and-deletion simulation, owner acceptance, and SHA/tag freeze are
complete. Pending #159 Slice B may add additional IQA tests/docs at their old
flat locations; normalize them into these owned leaves **before H1 approval**.
