# P7-D Stage 1 Release Publication Audit

Status: Active
Audited base: `main@1fa6d278fcb16ed5170c3a21fc8cb31119f6e7e2`
P7-C merge: PR #63 / `f3b1437b478e119c425dbf00d627b37f0371889e`

## Purpose

P7-D Stage 1 establishes **Release Metadata & Manual Publication Foundation** on top of
the merged P7-C owner-local release-candidate contract.

It does not add runtime update behavior, authentication, privileged publication, or a
second build/distribution path.

Canonical lineage:

```text
source
  ↓
P7-C validated release candidate
  ↓
P7-D Stage 1 publication validation / metadata
  ↓
CORPORATE SECURITY BOUNDARY
  ↓
authorized human
  ↓
corporate GitHub Enterprise Release
```

Manual authorized publication is the supported production workflow, not an automation
failure fallback.

## Repository audit

The merged P7-C implementation already owns the authorities P7-D must reuse:

- `src/pixelscope/version.py::__version__` — canonical application/release version;
- `scripts/release_contract.py::release_version()` — release-version reader;
- `scripts/distribution_contract.py` — target identity, canonical artifact naming,
  payload manifest, and file SHA-256 logic;
- `scripts/release_candidate_contract.py` — exact current P7-C candidate provenance
  schema, field constraints, and validator shared by candidate writing/publication;
- `scripts/validate_release_bundle.py` — exact four-file production bundle validation;
- `scripts/build_release_candidate.py` — exact source commit capture, release-note
  source/rendering, candidate staging, provenance, and P7-A/P7-B build/smoke reuse;
- `tests/unit/test_release_candidate.py` and P7-B release tests — executable regression
  coverage for those contracts.

P7-D Stage 1 therefore must not introduce a second candidate builder, provenance schema,
version parser, manifest authority, release-note renderer, or artifact hashing
implementation. Small shared helpers may be promoted from P7-C modules where publication
tooling needs the same behavior.

## P7-C contract preservation

The P7-C production bundle remains exactly:

```text
PixelScope-<version>-windows-x64.manifest.json
PixelScope-<version>-windows-x64-THIRD_PARTY_NOTICES.txt
PixelScope-<version>-windows-x64-portable.zip
PixelScope-<version>-windows-x64-setup.exe
```

P7-D Stage 1 consumes candidate staging under:

```text
release/candidate/PixelScope-<version>-windows-x64/
```

which adds the rendered `RELEASE_NOTES.md` and `release-provenance.json` beside those
four production artifacts. Stage 1 may create a separate provider-neutral
`release/publication/...` staging layer, but it must not weaken or redefine P7-C's
four-file release-root validation or provenance schema.

Before `release-provenance.json` crosses into publication staging, the shared P7-C
validator requires the complete current field set, rejects unknown fields, keeps tool
executable identities basename-only, requires repository-relative release-note identity,
requires canonical lowercase hashes/full Git commit identity, and requires an exact
production-artifact map matching staged files.

## Canonical publication identity

All publication identities derive from the canonical version:

```text
src/pixelscope/version.py::__version__
    ↓
version                 0.1.0
release tag             v0.1.0
release title           PixelScope v0.1.0
release-note identity   docs/releases/<date>-v0.1.0.md
artifact names          PixelScope-0.1.0-windows-x64-...
candidate provenance    version = 0.1.0
publication metadata    version = 0.1.0
```

The release tag contract is `v<canonical-version>`. A publication tag must resolve to
the exact source commit recorded by candidate provenance. Repository tooling may
validate that relationship but must not create or push a production tag automatically.

## Release-note contract

For a selected version there must be exactly one durable dated note source matching:

```text
docs/releases/<date>-v<version>.md
```

The source heading must identify `PixelScope v<version>` and retain the
`{{SOURCE_COMMIT}}` placeholder. P7-C renders the exact candidate source commit into the
staged `RELEASE_NOTES.md`. P7-D Stage 1 validates that:

- durable note identity/version matches the canonical version;
- staged notes contain no source-commit placeholder;
- staged notes contain the exact candidate provenance source commit;
- staged notes equal the canonical rendering of the durable note source for that
  commit;
- release title/tag/version remain consistent with the same authority.

## Publication metadata boundary

Provider-neutral publication metadata may contain only release identity/provenance
needed to validate an authorized manual publication, for example:

- schema version;
- product;
- canonical version;
- target;
- release tag and title;
- exact source commit;
- release-note source identity and SHA-256;
- rendered release-note filename and SHA-256;
- candidate provenance filename and SHA-256;
- exact production artifact filenames, sizes, and SHA-256 values.

It must not contain credentials, tokens, browser cookies, local absolute machine paths,
corporate secrets, or a hard-coded corporate GitHub host/repository URL that is not part
of the provider-neutral release identity.

## Manual publication procedure

After P7-D Stage 1 implementation is merged, actual publication evidence is generated
from a fresh candidate built from the exact owner-selected merged `main` commit.

Authorized publication checklist:

1. confirm the exact selected `main` commit and canonical version;
2. run the P7-C owner-local candidate build and require PASS;
3. prepare and validate P7-D publication staging;
4. confirm `v<canonical-version>` and `PixelScope v<canonical-version>` identities;
5. verify the local release tag resolves to candidate provenance `source_commit` before
   publication;
6. use the rendered candidate `RELEASE_NOTES.md` as the release note body/source;
7. upload only the approved production release assets defined by the publication
   metadata/checklist;
8. verify uploaded filenames, sizes/hashes, and candidate/publication provenance;
9. verify through the authorized corporate GitHub Enterprise UI/process that the remote
   release/tag resolves to the same exact candidate provenance `source_commit`;
10. verify the corporate GitHub Enterprise release visibility/access policy using the
    authorized human account;
11. record publication completion separately from the implementation PR evidence.

The local `--require-tag` check is pre-publication evidence only. It does not replace the
post-publication remote release/tag-to-source verification above.

Repository tooling stops at validate/prepare/render/hash/stage. It does not create the
production GitHub Enterprise Release, upload privileged artifacts, transfer restricted
files, use production credentials, or sign production binaries.

## Notification-only update discovery dependency — P7-D Stage 2

Runtime update notification is not part of Stage 1. The governing future rule is:

> **Update discovery must never initiate authentication.**

Stage 1 does not establish whether the eventual authoritative update-metadata provider
requires application authentication. If the selected provider requires authentication,
a future implementation may use only an already-established approved P6 capability and
must silently skip discovery when that capability is unavailable. If an authoritative
provider is explicitly usable without application authentication, this contract does not
prohibit that path.

Stage 1 establishes no common-IdP topology and no token interchangeability assumption
between corporate services. It therefore does not choose OAuth App, GitHub App, PAT,
bearer-token reuse, token exchange, browser-cookie reuse, or any other authentication
mechanism.

After the relevant P6/provider contracts are authoritative, Stage 2 may compare options
such as:

- IQA/PixelScope backend `GET /app/releases/latest` or equivalent;
- approved corporate platform metadata endpoint;
- corporate GitHub Enterprise Releases API using an approved GitHub authentication
  mechanism when that provider actually requires it.

No provider is selected by Stage 1.

An explicit future **View Release** user action may open an approved corporate release
page in the system browser. Browser authentication and repository authorization, if
required by that page, remain browser/provider concerns; PixelScope must not read/copy/
store browser SSO cookies.

PixelScope/IQA entitlement must not be equated with source/release repository
collaborator membership. A broader-access release repository or backend/platform
metadata endpoint may therefore be preferable later, but Stage 1 does not select one.

## P6 sequencing clarification

P6 production integration remains after P5-G. If authoritative corporate identity/
authentication guidance becomes available before the real P5-G environment, a P6-0
contract audit/research may proceed early. It must not implement production SSO, modify
Remote IQA authentication, issue/store tokens, or invent server contracts.

## Stage 1 non-goals

Do not implement in this Stage 1 PR:

- startup/periodic update checks or notification UI;
- Enterprise GitHub API client;
- GitHub OAuth/GitHub App/PAT;
- SSO login/token storage/token refresh;
- browser cookie access;
- IQA Authorization-header changes;
- Remote IQA auth changes;
- automatic download/install/installer launch/rollback;
- production signing;
- automated or privileged production publication.

## Evidence boundary

The P7-D Stage 1 PR proves publication metadata consistency, preparation/validation
mechanics, and durable manual procedure only. It must not claim that a production
release was published.

Actual production publication happens only after Stage 1 merge, a fresh P7-C candidate
from the selected merged source commit, and explicit authorized owner action.
