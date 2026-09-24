# User Guide follow-up work packages

The searchable User Guide foundation is now merged. Follow-up work keeps application Help integration, release packaging, hosting, and agent-facing extensions as separate contracts.

## WP-Help-A — Application Help integration

Status: **merged in PR #87**.

- **Help > User Guide** is installed by the production application composition.
- Frozen/release builds resolve the local entry point relative to the executable as `help/index.html`; the application does not depend on the process working directory.
- Source runs can open an already-built `site/index.html` and may also consume a local `help/index.html` bundle.
- The local page is handed to the platform through `QDesktopServices` rather than embedding a browser engine or introducing QtHelp/QCH.
- A build without a local bundle reports that the User Guide is unavailable instead of guessing an online location.
- Focused tests cover path resolution, Help-menu placement, idempotent installation, and local-file URL handoff.

Online Documentation remains dependent on WP-Help-C establishing an authoritative deployment URL. F1/context-sensitive routing remains deferred until the static local Help path has shipped and proved stable.

## WP-Help-B — Fully local documentation build and packaging — merged in PR #90

**Non-negotiable security contract:** the User Guide must build from checked-in files plus a
preinstalled documentation toolchain, even when individual external URLs are blocked. A
previously warmed MkDocs privacy cache, permitted CDN access, symlink privileges, or
internet access on the release machine must not be prerequisites.

- Replace the current CDN-based iframe-worker polyfill with a versioned, checked-in local
  JavaScript asset. Preserve working `file://` search; do not disable the offline plugin,
  substitute a no-op shim, or merely silence privacy-plugin warnings.
- Investigate the current build-time Mermaid CDN fetch. If no supported User Guide page
  uses Mermaid, remove its dependency without introducing an unbundled runtime URL.
  Otherwise vendor the exact required script locally.
- Record upstream version, source, license/attribution, and a reproducible content hash
  for each vendored third-party asset. Avoid downloading arbitrary mutable CDN content
  during routine documentation builds.
- Make `mkdocs build --strict` work after clearing `site/` and
  `.cache/plugin/privacy/` with outbound network access blocked. Include a deterministic
  test/CI job that prevents outbound requests during the build, not just an assertion
  that HTML is free of CDN links after a network-enabled build.
- Extend the generated-site contract to cover all runtime-loaded HTML, CSS, and JS
  references and to detect missing relative assets, especially the search shim.
- Consume the validated, self-contained `site/` as a release input for the offline
  `help/` bundle. Include it in portable ZIP and Inno Setup artifacts at the exact
  executable-relative path `help/index.html`.
- Validate offline search, navigation, screenshots, and relative links in installed
  and portable builds on Windows without network access.
- Documentation packages remain build-time dependencies, never PixelScope runtime
  dependencies. If the package installation itself must occur air-gapped, provide an
  approved internal package index or a prebuilt, pinned wheelhouse; this bootstrap is
  separate from the requirement for a network-free MkDocs build once installed.

Implementation notes for this work package:

- An exact published iframe-worker 1.0.4 shim is checked in with MIT license,
  upstream provenance, and an executable SHA-256 integrity check. The configured
  polyfill points to the local file and the privacy plugin is no longer needed.
- The existing User Guide does not use Mermaid diagrams; no CDN-based Mermaid
  file is part of the normal documentation build. Future Mermaid usage must
  preserve the same network-free build contract.
- CI invokes strict MkDocs with socket connections denied on both Windows and
  Ubuntu, after deleting generated site and privacy cache.
- Release build generates the site using the documentation environment, then
  copies the validated files to `dist/PixelScope/help/` beside the executable.
  The existing portable/installer pipelines retain the single canonical onedir
  payload; artifact validation requires the bundled Help.
- The generated 404.html is reserved for hosted documentation, excluded from
  the local executable-relative bundle because its root-relative URLs do not
  work through `file://`.
- The owner reported the full Windows release/portable/installer smoke PASS
  for PR #90; GitHub's documentation CI is not evidence of an installer smoke run.

## WP-Help-C — Optional documentation publication — merged in PR #91

- Produce an explicitly initiated, validated and version-identified static site
  artifact from the existing User Guide source. Preserve release provenance
  independently of P7 application release artifacts.
- Support manual GitHub Pages publishing **only** when the repository owner
  enables the Pages destination and explicitly opts in. Otherwise the same
  site artifact can be moved to an approved enterprise/internal static host;
  docs build, release and local Help remain independent of Pages.
- Restrict publication source to merged `main` or the matching canonical
  `v<version>` release tag and record the exact commit, version, inventory
  and hashes. Do not automatically create tags or claim permanent HTML archives.
- Define 14-day Actions transfer-artifact retention (or stricter platform
  policy), manual rollback, and the distinction between current live docs
  and historical source in Git. See `docs/USER_GUIDE_DEPLOYMENT.md`.
- Prepare a separately gated **Online Documentation** action, which remains
  disabled until an actual approved HTTPS site URL is configured in a
  reviewed code change. Never fall back from local Help or reuse SSO tokens.
- Fix the prior #90 reviewer P1: validate all local HTML navigation links,
  not just generated `llms.txt` routes and resource references; reject
  hosting-only 404 pages in an offline installed bundle.

## WP-Help-D — Agent interface — merged in PR #92

The merged WP-Help-C offline/static publication pipeline was the prerequisite.
WP-Help-D delivered an agent-facing **retrieval interface**, not a chatbot:

- Expand the existing static `llms.txt` to cover every canonical User Guide
  navigation route and keep its generated HTML paths under the same strict
  site validation. Do not invent a new protocol or duplicate Markdown.
- Provide a deterministic repository-local User Guide search CLI with text and
  bounded JSON results, source-relative path/line citations and generated site
  routes. It reads the canonical Markdown only and needs no network, credentials,
  local image files, embeddings, or runtime application dependency.
- Lock down coverage with focused tests and documentation CI; keep offline Help,
  manual publication, and P7's release-bundle contract unchanged.
- Evaluate Ask PixelScope separately in
  [Agent interface](USER_GUIDE_AGENT_INTERFACE.md). An optional model/RAG
  experience requires a justified UX, source grounding, privacy/security design,
  provider approval, and a distinct owner decision. Do not add one by default.

The repository-side search tool is not shipped as a new application feature;
installed users retain their existing local Help/search without an AI service.

## Deferred Help/navigation follow-up

- F1/context-sensitive Help remains a UI navigation topic (not WP-Help-D agent work).
- Add explicit tests for the missing-bundle and browser-open failure messages in
  the earlier Help integration without changing their user-facing behavior.

## Deferred/non-goals

No embedded PyQt Help window, QWebEngineView, QtHelp/QCH, chatbot, RAG server, Remote LLM API, implicit online fallback, or context-sensitive F1 routing is part of WP-Help-A. Installer bundle integration is owned by WP-Help-B.

## WP-Help-E — Automated Screenshot Lifecycle — E0–E4 merged / E5 in progress

E0 is a planning-only follow-up to merged WP-Help-A/B/C/D (#87/#90/#91/#92).
The [WP-Help-E execution plan](exec-plans/active/wp-help-e-automated-screenshot-lifecycle.md)
records the existing real-QWidget capture implementation, tracked screenshots and
missing scenes; a single Screenshot ID manifest; PR impact selection and conservative
fallback; pinned-main/head visual diff; separate Documentation CI and Screenshot CI;
reviewed image provenance; security, Windows Qt lifecycle and release boundaries.

**Gate:** E1 first proves real screenshot capture on a Windows GitHub-hosted runner
using isolated scenarios. No hosted-GUI feasibility or Issue #81 native-crash fix is
claimed by E0. If the PoC fails, revise the remaining WP sequence and obtain owner
approval for another execution environment before implementing a full screenshot CI.

The proposed sequence is E0 plan → E1 isolated capture/Windows PoC → E2 manifest/
scenario contract → E3 conservative impact analysis → E4 pinned baseline/head visual
diff and PR artifacts → E5 conditional MkDocs screenshot rendering and independent
documentation validation → E6 human approval/provenance/release policy. E5 can proceed
in parallel with E3/E4 after E2 settles the manifest schema. Each implementation WP
uses a separate reviewed PR; image candidates never auto-commit and PRs never
self-merge. Existing screenshot guidance remains at
[user-guide/assets/screenshots/README.md](user-guide/assets/screenshots/README.md).

E0 planning was merged as PR #93. E1 implements a limited, isolated Windows real-GUI
capture feasibility probe for Single View and RAW profile dialog, with two fresh
capture attempts per scenario, PNG/metadata artifacts and explicit native-failure
reporting. It does **not** yet replace the seven approved guide screenshots,
produce a manifest or activate change-impact Screenshot CI. E1 success requires
inspection of actual hosted Windows PNGs and repeatability; static checks alone
are not evidence of GUI availability or a fix for Issue #81.

E1 was owner-approved and merged as PR #94 at `main@ec8563df821a77b270363b00cff83e6c97e9db07` after Windows-hosted PoC, documentation CI and reported owner Windows validation. This proves only the two isolated capture scenes; Issue #81 is not marked resolved. E2 introduces a versioned seven-legacy/seven-planned Screenshot Manifest, classifies legacy-only scenes and three diagnostics, and adds Qt-free inventory/PNG/reference checks. E2 **does not yet** enable Screenshot ID Markdown insertion, missing-PNG omission, E3 impact mapping, E4 visual baselines or E6 promotion; these retain their separate review gates.

### E2 completed / E3 impact selector

E2 PR #95 merged at `main@415dab7cf4742cce0d6369024cdc91da652556d7` after owner full-pytest and live Help/image-rendering smoke PASS. Owner also observed that **some existing guide screenshots appear older than current UI**. This is tracked as screenshot-content review/replacement debt in E4–E6, not proof that guide instructions are incorrect; existing `legacy-unverified` PNGs must not be called current, automatically replaced or assigned invented capture commits.

E3 owns Qt-free source-file change impact inference with verified per-scene ownership, shared shell/fixture mapping, conservative unknown UI/core/io fallback, renames/deletions and committed PNG changes. It is distinct from actual E4 Windows comparison and E5/E6 User Guide image migration/promotion.


### E3/E4 merged; E5 source-marker migration

E3 impact-selection PR #96 merged at `main@5e5a418d19393560f484f332d2c64a5cc0149526`.
E4 pinned real-Windows baseline/HEAD comparison PR #97 merged at
`main@985e69d6dd1840cbf5b0739be8ca29b758c36cdc`, following independent
blocker-free review and owner-reported full local Windows pytest PASS. E4
generates read-only, inspectable candidate PNGs/reports; it does **not** prove
seven legacy screenshot captures are current or approve/promote any of them.

E5 migrates the six topic-page literal PNG image links to canonical manifest
Screenshot ID markers. The Qt-free manifest checker verifies source placements
and real committed PNGs; the same checker executes before direct strict MkDocs
builds. A declared missing PNG is omitted from web and installed offline HTML
without a broken link or altered source explanation. All unrelated documentation
links remain under the existing whole-repository `check_docs.py` validator.
E5 separately tests all seven declared historical PNGs removed one at a time
from a full repository copy under network-blocked strict MkDocs builds. The
floating Plots PNG stays declared but has no invented topic placement.

E6 still owns fresh current-UI candidate review, explicit owner approval,
screenshot byte promotion, trustworthy provenance and per-gap closeout of the
seven not-yet-automated scenes. E5 was owner-approved and merged as PR #98 at
`main@0381d4e69df82f060dc4917b4117f68b8cebc574`. The new
[E6 owner review procedure](exec-plans/active/wp-help-e6-owner-review.md) and
[14-ID decision inventory](exec-plans/active/wp-help-e6-coverage-decisions.json)
deliberately record no blanket acceptance: `python scripts/audit_ui_screenshot_coverage.py`
reports unresolved images without inventing approvals, and
`--require-complete` fails until per-ID review decisions are made. Neither E5 nor CI changes approved PNGs
automatically; Issue #81 remains a separate lifecycle task.
