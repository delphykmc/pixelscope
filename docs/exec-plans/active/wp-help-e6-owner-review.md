# E6 owner review: real PixelScope screenshot promotion

E6 begins after owner-authorized E5 PR #98 merged at
`main@0381d4e69df82f060dc4917b4117f68b8cebc574`.
**Current state (2026-09-25):** all 14 PNGs were visually approved and promoted
in Draft PR #99 at `68ed33412a17711ed549793cfab6f8d9e9cd3397`, from
capture source `631779bb91278e846f39e376dd1bef8210df1e5c`. The 14 decision
records are `promoted` and the read-only audit reports `complete: true`.
This does **not** close the outstanding external exact-byte attestation,
candidate-sidecar verification or post-merge history/release acceptance.
The superseded E6-entry inventory below is preserved as historical context;
never invent the old seven PNGs' original capture SHA.

## Historical E6 entry inventory (superseded by current promotion)

| Group | Screenshot IDs | Current proof | Next action |
| --- | --- | --- | --- |
| Verified isolated capture | `single-image`, `raw-profile-dialog` | Real Qt Windows hosted E1/E4 capture, but not yet current-guide owner acceptance | Re-run at an exact pinned current code revision; present old and candidate + report |
| Legacy manual, not isolated | `six-image-multiview`, `difference-analysis`, `histogram-docked`, `line-profile-docked`, `plots-floating` | Older real app PNGs and ten-scene manual capture implementation; no per-scene Windows isolated success claim | Add tested real isolated scene or run a carefully isolated owner-local approved capture, confirm readiness/cleanup and visually inspect |
| Unfilled User Guide coverage | `window-overview`, `files-workspace`, `roi-exact`, `statistics-workspace`, `settings-dialog`, `iqa-neutral`, `yuv-profile-dialog` | Manifest/ownership/page targets only; no registered capture builder | Each: implement real, public-safe capture + tests and obtain owner approval, **or** record individual owner-approved technical defer and follow-up |

The existing `scripts/capture_ui_review.py` calls `QSettings().clear()` on the
process's default settings and captures ten scenes in one native process; do
not invoke it against the owner's personal app configuration or treat its
fixed waits as proof of calculation readiness. A normal owner desktop
screenshot may contain company-specific paths, filenames or accounts and
must be checked/redacted **before** uploading anywhere. Do not use
generated/reconstructed UI images as substitutes for Qt `QWidget.grab()`.

## Owner decision for each candidate (explicit; no implied batch consent)

Show one Screenshot ID at a time, including its canonical page, legacy image
(if any), real current candidate, artifact + full immutable source SHA,
captured application version, intended viewport, capture profile, PNG SHA-256
and visible labels/controls. Use base/head/diff when comparable; treat small
renderer jitter and `BASELINE_INCOMPATIBLE` as review evidence, not an
automatic stale/current judgment. Ask the owner to record one of:

- **Promote:** the exact candidate PNG bytes and provenance were visually
  accepted for the specified Screenshot ID. Link the *existing* owner review
  comment that quotes both capture source SHA and PNG SHA-256.
- **Retain:** the legacy screenshot is still suitable, with a concrete reason
  and an owner review reference. Keep `legacy-unverified` and its historical
  capture SHA unknown: this is not a newly approved capture.
- **Defer:** the candidate cannot yet be approved. Record a specific technical
  blocker/recapture need, external owner review reference and concrete
  follow-up issue; a generic seven-scene deferral does not close coverage.
- **Reject:** do not copy the PNG, change status or move on as if approved.
  Revise the real-UI scene, recapture and re-present the new SHA.

Record only actual decisions in
[`wp-help-e6-coverage-decisions.json`](wp-help-e6-coverage-decisions.json).
The E6 initial inventory deliberately marked **all 14** IDs `pending` without
fabricated owner evidence. At the current PR HEAD all 14 are `promoted`. Run:

```powershell
python scripts/audit_ui_screenshot_coverage.py
python scripts/audit_ui_screenshot_coverage.py --require-complete
```

The normal audit checks all individual decisions, and `--require-complete`
requires no pending IDs and consistent manifest bytes/provenance. It now
passes on Draft PR #99 following the owner's visual approvals. The audit does **not** verify
the real human identity behind a URL; that is an explicit PR review step.

## Promotion and final release gate

The dedicated candidate import/verification step must fail closed on wrong
Screenshot ID, scenario, PNG bytes/hash, source SHA, app version, renderer
profile/geometry, changed current image, unexpected manifest page mapping,
approval reference or extra files. Bind approved PNG+manifest content to the
real prior owner review; keep the old history in Git. Never commit an image
merely because a candidate artifact exists or the E4 result is `CHANGED`.
The introducing Git commit depends on its content: derive it **after merge**
from Git history/blobs, not an imagined `approval_commit` field in its own
manifest. Test merging/rewording/squashing without invalidating content
identity. E6 code review and owner authorization for PNG promotion and merge
are separate decisions.

Finish with documentation/site checks, Windows real GUI scene tests, actual
Windows full pytest, and the owner opening the packaged `help/index.html`
in both portable/installer builds and inspecting six topic images plus any
newly approved gap pages. Validate a release-tag checkout builds using
the exact reviewed PNG and manifest; no new public URL, automatic publication,
installer shape changes or resolution claim for Issue #81.

## Final exact-byte attestation and original capture packet

Review the per-ID approved PNG SHA list in
[`wp-help-e6-approved-image-hashes.md`](wp-help-e6-approved-image-hashes.md).
Only the owner can confirm these *exact bytes* are those visually accepted;
matching manifest hashes alone proves integrity but not what a human saw.
The SHA list can be checked from GitHub on any OS and requires no new capture.
The original owner-local capture PNGs and their `*.json` sidecars (not a
new runner recapture) are needed for a source-sidecar identity verification.
Hosted Windows GUI captures from a different machine may be visually equivalent
but differ at the byte level and must not be substituted as provenance for the
14 owner-local PNGs. Until the original packet is independently matched,
source-sidecar verification must be reported as **pending**, not PASS.

### Local original-packet verification (only if Codex kept the original files)

The committed PNG SHA-256 list and the capture-source Git commit can be
checked through GitHub on any OS; **no new Windows capture is required** for
that review. Only the owner can attest that the listed bytes are the images
already approved visually. The historical original capture sidecar check is
separate: if Codex's source-SHA-qualified PNG/JSON packet remains on the local
Windows disk, run from PR #99's checkout (Python 3.10, no Qt import required):

```powershell
cd C:\\path\\to\\pixelscope
git checkout feature/wp-help-e6-reviewed-screenshot-promotion
python scripts/verify_ui_screenshot_capture_packet.py --packet-dir "C:\\path\\to\\original-e6-captures"
python scripts/audit_ui_screenshot_git_history.py --ref HEAD
```

The packet directory must contain matching `<scenario>-1.png` and
`<scenario>-1.json` (or `<screenshot-id>.png/json`) for all 14 original
locally approved captures. The verifier requires *exact byte equality* with
the committed PNGs, original capture sidecar source SHA, app version, scenario,
profile, image SHA, fixture and QWidget dimensions. It is read-only: no PNG
or manifest will be copied, approved, recaptured or mutated. Do not substitute
a newer GitHub-hosted runner packet if its PNG hashes differ from the local
approved pictures, even when both were rendered at the same code SHA.

After merge, derive introducing commits from the **actual merged history**,
and verify the eventual release tag as an independent immutable snapshot:

```powershell
git fetch origin --tags
python scripts/audit_ui_screenshot_git_history.py --ref origin/main
python scripts/audit_ui_screenshot_git_history.py --ref origin/main --release-ref <actual-release-tag>
```

Do not run a made-up future release tag or claim post-merge validation before
it exists. The old historical tag still must validate against *its own*
manifest/image bytes, so a future E6 screenshot cannot rewrite rollback data.
