# E6 owner review: real PixelScope screenshot promotion

E6 begins after owner-authorized E5 PR #98 merged at
`main@0381d4e69df82f060dc4917b4117f68b8cebc574`.
It is **not complete** merely because the MkDocs hook renders existing images
or the Windows GUI comparison workflow passes. The seven historical screenshot
files retain their unknown original capture SHA; never backfill one by guessing.

## What exists versus what remains

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
The initialized file deliberately marks **all 14** IDs `pending` without
fabricated owner evidence. Run:

```powershell
python scripts/audit_ui_screenshot_coverage.py
python scripts/audit_ui_screenshot_coverage.py --require-complete
```

The normal audit succeeds while reporting unresolved IDs; the completion
flag deliberately fails until all decisions are individually recorded
and consistent with manifest bytes/provenance. The audit does **not** verify
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
