# W09a — Review v1 local schema and atomic repository

Status: implementation candidate for **independent exact-HEAD Qt-free review**.
Parent: #210, W00 technical contract §§4–6 and §11 B1/B2/H2/H3.
Baseline main: 44c9e53df2b6bc074444b2291f27e2c9f38c8ecc.

## Separation and authority

- Local extension: .pxreview. JSON kind: pixelscope-review, schema_version: 1.
  This is NOT the existing .pixelscope Session v1 schema or restore command.
- The Qt-free record contains UUID, app version, UTC times, source identities,
  native interpretation and fingerprints, optional private locator, ordered
  source/selection intent, named findings and exact W04 ReviewViewStateV1 DTO.
- A Finding retains UUID, timestamp, Unicode title/note/tags, role/pair, ROI
  and line in reference coordinates, channel/gain/Difference recipe and W02
  immutable portable analysis context or explicit unavailable reason.
- Native signature is the W02 profile digest plus native/reference shapes,
  dtype/layout/effective bits and W02 native interpretation allowlist.
  Size, basename and mtime are NOT source identity.
- W02 context serializer/parser and W04 DTO serializer/parser are reused.
  W02 ephemeral runtime document identities are never persisted.
- Strict captured-evidence policy: W02 ROI/scope and channel MUST match the
  named Finding; the complete W02 source native interpretation and any present
  digest MUST match the saved ReviewSource for the same UUID. W04 reference
  geometry MUST match every ReviewSource reference_shape, not just the W04
  page-internal shapes. W02 Difference captures additionally require an exact
  ordered reference/target pair, channel, region and non-null cache identity.
  These checks are not an independent attestation of Difference mode/threshold:
  W09b must establish that from the exact currently presented request/token.
  Otherwise store an explicit unavailable record rather than misbind evidence.
- All programmatically supplied record collections are normalized to immutable
  tuples; the terminal newline is included in the Review byte budget.

## Strict JSON limits

| Property | Limit / behavior |
|---|---|
| Review JSON | 16 MiB UTF-8 including trailing newline |
| JSON depth | 48 |
| Sources | 10,000, unique canonical lowercase UUIDs |
| Findings | 1,000, unique canonical lowercase UUIDs |
| Per-finding sources | 1–6 |
| Per-finding analysis captures | 16 |
| Title / note | 256 UTF-8 bytes / 32 KiB |
| Tags | 32 unique, each 256 UTF-8 bytes |
| Local-only extensions | 64 KiB |
| Nonfinite | explicit W02 metric state only; invalid bare JSON numbers rejected |
| Future version, unknown critical fields, duplicate JSON keys | fail closed |

Optional local locator.local_path requires document allow_local_paths=true,
which W09b must secure through explicit consent. Relative path hints reject
absolute paths, drive/UNC roots, and traversal. Local paths never project into
portable reports.

PortableReviewProjectionV1 is a separate positive-allowlist DTO. Its default
projection pseudonymizes names as Source 1, Finding 1 etc., excludes private
paths, local extensions, user-authored titles/notes/tags and raw profile paths.
Explicit disclosure arguments must be gated by a W10 UI preview. W10 still
owns typed metric projection, HTML/PNG/manifest allowlists and ZIP leak tests.

## Repository API

- ReviewRepository.load_with_revision(path) returns (ReviewDocumentV1, SHA256-ETag).
- ReviewRepository.load(path) returns the validated ReviewDocumentV1.
- ReviewRepository.save(path, document, overwrite=False,
  expected_revision=None, cancel=None, protected_paths=()) returns
  ReviewSaveResult(path, revision_sha256, committed=True).

Writer validates before touching disk, appends extension before all collision
checks, rejects symlinks and protected source paths, uses a same-directory
exclusive temp, write/flush/fsync, and atomic exclusive hardlink publication
for create-only. Hardlink-unsupported filesystems fail closed, never replace
an existing file. Updating uses os.replace only after explicit overwrite,
same Review document ID and matching prior SHA-256 revision; sibling exclusive
lock files serialize cooperating processes, and local locks serialize threads.
Stale lock files are not automatically stolen. Existing Session/other Review,
read-only, Windows-locked, permission failures and revision races are rejected.
Directory fsync is attempted where supported. Failed/cancelled pre-publication
saves clean staging files and leave destination unchanged. Cancellation after
the publication point is reported as committed, not rolled back. External
non-cooperating writers cannot be forced to honor advisory locks.

## Source verification API

- stream_source_sha256(path, cancel=None, progress=None, max_bytes=None)
  returns SHA-256 and advisory file metadata, using bounded 1 MiB chunks.
- verify_review_source(saved, candidate_path, native_signature,
  confirmed_by_user=False, cancel=None, progress=None, max_bytes=None)
  returns SourceResolutionV1.

Statuses: verified; candidate_unverified; changed; missing; unsupported_profile.
Only verified permits binding of old source identity, requiring exact SHA-256
AND exact native interpretation. User consent is mandatory for every relocated
candidate, even if hash matches; it is never sufficient without a hash.
The Source Verification trust boundary is now an explicit abstract
CandidateNativeDecoderV1 adapter, NOT an arbitrary callable. Its
`decode_signature(probe: CandidateDecodeProbeV1)` method receives the exact
candidate absolute path, immutable opened-file revision and a restricted
read/seek stream tied to the same file handle used for SHA-256. Returning a
cached DTO, a lambda, or an adapter that reads ZERO bytes never results in
Verified; mismatched actual signatures are unsupported_profile and a changing
source revision is candidate_unverified. Hashing uses 1 MiB streaming chunks
and checks descriptor/path identity before/after decoder reads. Verified
requires both SHA-256 and the native signature to match, plus relocation
consent when appropriate.

**Trusted adapter caveat:** byte consumption is a necessary but not a sufficient
proof of semantic decoding. Python cannot establish that an arbitrary decoder
actually derived every native profile field from those bytes. W09b MUST supply
an independently reviewed, application-owned native decoder adapter that uses
the selected RAW/YUV/profile interpretation of the candidate, not a cached
Review/Document signature. W09a's synthetic byte-dependent test adapter is
NOT production authorization. Until that W09b integration and review gate,
no Qt workflow may claim historical source verification. No auto-search,
auto-relink or silent replacement is implemented here.

W09b restore must activate a finding only when ALL referenced source keys,
including Reference/Primary, are verified. Unverified/missing/changed findings
remain immutable offline evidence, not current calculations. The adapter must
stage and validate before committing canonical registration/selection,
validate reference bounds/epoch and loaded gains/layout, preserve stale
Difference as uncalculated and report partial post-commit failure truthfully.
No UI or Session v1 modification belongs to this PR.

## Verification commands (owner Windows CPython 3.10)

- python -m pytest -q tests/unit/test_w09a_review_repository.py
  tests/unit/test_review_view_state.py tests/unit/test_review_analysis_bundle.py
  tests/unit/test_comparison_set.py
- ruff check on changed modules; ruff format --check on changed modules;
  mypy on changed modules; scripts/check_docs.py; git diff --check.
- Full normal-GC Windows suite, Windows file locking/read-only behavior and
  native UI restoration remain separate acceptance gates. Do not claim PASS
  without actual observed results.

W07 ownership is unaffected; no MainWindow, Viewer, Session v1, W07 panel
or W09b UI code was edited.
