# User Guide online publication

WP-Help-C provides an **optional, explicit** static-documentation publication path.
It does not change the canonical Markdown, require any GitHub Pages capability on
the development/release host, or replace `Help > User Guide`'s installed
`help/index.html`. Documentation site publication is **not** the P7-D
application release publication contract.

## Security and activation boundary

Do **not** infer that GitHub Pages is enabled, reachable, corporate-approved,
or appropriate for the User Guide merely because a repository exists.

- A designated owner must review the content and screenshot visibility before
  choosing a public or internal hosting destination.
- The workflow is **manual only**; pushing `main`, creating a release tag,
  publishing a GitHub Release, or opening a PR cannot publish documentation.
- Repository Actions variable `PIXELSCOPE_DOCS_PAGES_ENABLED=true` is required
  **only for the Pages target**. Pages must also be explicitly enabled in repo
  Settings > Pages with GitHub Actions as the source. Apply environment protection
  / required reviewers to `github-pages` where supported.
- If Pages is disallowed or unavailable, choose the `artifact` target; no Pages
  permissions or setup calls are required. Authorized staff can upload the
  exact extracted `site/` to an approved internal static server instead.
- A *real*, reviewed online URL is not yet configured in the application.
  The opt-in `ONLINE_DOCUMENTATION_URL` constant in
  `src/pixelscope/ui/user_guide_help.py` stays `None` until the owner
  verifies an authoritative HTTPS site and approves an application change.
  Only then will Help expose **Online Documentation** separately from the
  existing local **User Guide**. The local action never falls back to the
  network; no SSO cookies, credentials, or user data are accessed.

## Manual workflow

After this work package is merged into the default branch:

1. Choose **Actions > User Guide publication (manual) > Run workflow**.
   Run the *workflow* on `main`; its `revision` input selects the content
   source. Select `main` or an existing `v<canonical-version>` Git tag.
   For a release tag, the version in that commit's
   `src/pixelscope/version.py` must match the tag exactly.
2. Select `target=artifact` for offline/internal publishing preparation.
   Optionally choose `target=pages` only after Pages/Actions/environment
   permission and public/internal audience approval. A Pages request without
   the repository opt-in fails with an explicit diagnostic.
3. The workflow first checks out the **trusted dispatched main SHA** and
   runs `scripts/validate_user_guide_publication_ref.py` from that checkout
   using the runner's Python. It rejects arbitrary branches, pull refs and
   ref expressions **before** checking out or installing requirements from
   any selected source. For tags, it verifies a strictly formatted
   `v<version>` ref, a commit in the trusted main history, the matching
   literal `__version__` without executing tag code, and publication tooling
   files present in that commit. Only then does the workflow check out the
   **validated full SHA**, install build-time documentation packages and run
   strict MkDocs. Publication staging rechecks the exact preflight SHA and
   validates local assets and HTML navigation, then stages:

   ```text
   build/user-guide-publication/
     publication.json
     site/
       index.html
       llms.txt
       search/
       assets/
       ...
   ```

4. The downloadable `pixelscope-user-guide-<version>-<full-commit>` Actions
   artifact contains the static site and `publication.json`. The manifest
   records exact Git commit, selected ref, application version, and each site's
   size/SHA-256. Check the source ref and inventory before copying **only**
   `site/` to the approved internal server's static root.
5. When `target=pages`, the workflow uploads **that same staged site/** to
   Pages and deploys only in the separate `github-pages` protected environment.
   The Pages URL comes from the actual deployment result, never from an
   inferred `github.io` hostname. Confirm the page loads via the approved
   browser/account, the search index works and screenshots/relative URLs render
   at the real base path. Check access restrictions on the resulting page.
6. Record approved hosting address, visibility, owner, publishing commit,
   version, deployment date, and rollback route in the authorized team channel.
   Activate `ONLINE_DOCUMENTATION_URL` through a separately reviewed code
   change only after verifying the deployed HTTPS URL.

No production deployment is implied by a successful publication *implementation*
PR or a passing docs CI check.

## Versioning, rollback, and retention

- **Current docs**: a deliberate `revision=main` publication represents
  current merged documentation at its recorded exact source commit.
- **Release docs**: protect/approve release tags under repository policy;
  an existing annotated/lightweight
  `v<canonical-version>` tag containing the WP-Help-C publication tooling may
  be selected to reproduce a version-specific site. Tag commits must be
  ancestors of the dispatched trusted main commit. Tags are created/approved
  by the separate P7-D release process, **not** by documentation automation.
  The selected tag must resolve to the commit being built. Older tags lacking
  this tooling need an individually reviewed manual historical-documentation
  procedure; the workflow does not silently mix historical content with
  newer publication code. Do not attach new assets to the four-file P7
  production bundle.
- **Live Pages root**: one site at a time, not an implicit multi-version
  archive. Manually running a previous approved tag is a rollback, and its
  deployment replaces the currently live root. Record this in the release log.
- **Download artifacts**: request 14-day Actions retention, subject to stricter
  organization/Enterprise policy. These are transfer artifacts, **not**
  long-term release records. Keep durable Markdown/history in Git; if historical
  published HTML must remain available, use approved internal storage/hosting
  with a separate documented retention policy and content classification.
- Publishing must never modify `docs/user-guide/`, `site/` used for the
  local release, application versions, signed installers, P7 candidate metadata,
  or installed local Help.

## Internal static hosting checklist

Serve the contents of staged `site/` at an approved HTTPS path. Preserve the
relative directory tree and expected MIME types (HTML, CSS, JavaScript, SVG,
PNG, JSON); `use_directory_urls: false` supports subpath hosting. Test at
least `index.html`, another feature page, navigation, screenshots and
search. The generated `404.html` is hosting-only; if the server uses a
project subpath, verify its absolute URL references or supply a correctly
configured server-specific 404 page. It is intentionally absent from the
installed `file://` Help bundle.

If the host is unavailable, **Help > User Guide** must still work offline.
