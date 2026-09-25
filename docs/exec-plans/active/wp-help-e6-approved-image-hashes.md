# WP-Help-E6 — exact approved screenshot byte identities

**Owner-attested hash listing.** The owner explicitly confirmed all fourteen IDs and SHA-256 values as the exact PNG files viewed and approved in the temporary User Guide in [PR #99 owner exact-byte attestation](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5828359533).

- Source code at actual local capture: `631779bb91278e846f39e376dd1bef8210df1e5c`
- Draft PR #99 promotion commit at initial image approval: `68ed33412a17711ed549793cfab6f8d9e9cd3397`
- Initial visual approval comment: [PR #99 owner approval](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5827211017)
- Screenshot format: existing real PixelScope QWidget PNGs, not synthesized UI.
- Each hash below is **from the approved manifest at the PR branch**, whose PNG byte integrity is already checked by `scripts/check_screenshot_manifest.py`.

| Screenshot ID | Exact SHA-256 | Committed PNG |
| --- | --- | --- |
| `single-image` | `75dc3be635ac5e27b93b10a3590bfb9338da063cdb750de1e777d5bfaf31765c` | `single-image.png` |
| `six-image-multiview` | `9427c502776e4c1692c1e9d5ef9fcb3fa6ee28c28f32a39ec70290d29e2eb945` | `six-image-multiview.png` |
| `difference-analysis` | `77ed5d0e9f1ed7ead96cd27de2b19f5829dd108ecc56d1ac5cc08f97f01e14a5` | `difference-analysis.png` |
| `histogram-docked` | `611990dbc4d0ed008ef3d016fbc25db42dc1a935bbad58a1ef985b1868e08776` | `histogram-docked.png` |
| `line-profile-docked` | `d015b4d690bc9d6d8ee095e6a8f298f4f5a7caca213c653487e0b62930afe270` | `line-profile-docked.png` |
| `plots-floating` | `39f2632a4044e12dcb63a90e85a2bbb5f5903e4a7b07b72df443a4b2ccde8e98` | `plots-floating.png` |
| `raw-profile-dialog` | `637420c42709e37d5adf0756a0c046c5f42e686d608fff77f78564c59dde2dae` | `raw-profile-dialog.png` |
| `window-overview` | `6b7dc3f1404ef2bd26b5da5d6c7bf93c1af80e329eac4c6a54e69beb44db8549` | `window-overview.png` |
| `files-workspace` | `3346f5c561de5d1e43143e7593ea3bf5f6b43bbae26007293d98c1d1618ab7f7` | `files-workspace.png` |
| `roi-exact` | `c879ea98a72be0cf3ec728aa91ced2316c9ef0d93222d701491a00c4913cacf4` | `roi-exact.png` |
| `statistics-workspace` | `a3430f6d27773c7fe10db1cfd886166b81fecf5911dbf7bbec849961e995157e` | `statistics-workspace.png` |
| `settings-dialog` | `fb6a2f25428990107f8163cea1973421d8671cd1cd7bafba21144949d8b0bcdd` | `settings-dialog.png` |
| `iqa-neutral` | `691b940cac980bc2be89dfda0ad389b886d62074a7c40f3c2f57db5b5f49f6b9` | `iqa-neutral.png` |
| `yuv-profile-dialog` | `e7d87c656c5ff3bfce76324e7dcbefd03aa692938e3219076a1b47abb07e08fc` | `yuv-profile-dialog.png` |

**Owner evidence gate — satisfied:** the explicit [exact-byte approval](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5828359533) names this hash list and capture source `631779bb91278e846f39e376dd1bef8210df1e5c`. Each manifest `approved.approval_ref` and each E6 decision `review_ref` points to that comment. The original [visual review](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5827211017) remains as prior evidence. Future PNG byte changes require fresh visual approval and a new hash-specific owner reference.

**Original local capture packet — independently reported PASS:** [2026-09-25 Codex/owner local verification](https://github.com/delphykmc/pixelscope/pull/99#issuecomment-5828441867) reports the original 28 PNG and 28 JSON sidecars checked at PR source `8d01bf6f87b7eb365b94f6c8293cfa4b7d6a134f` with `scripts/verify_ui_screenshot_capture_packet.py`: `E6 original capture packet PASS: every approved PNG matches original sidecar.` The packet stays owner-local; CI-hosted re-captures are not a substitute for those exact PNG bytes.

**Capture provenance is a different gate.** Local candidate sidecars from the
original `631779bb91278e846f39e376dd1bef8210df1e5c` capture must independently agree with the matching
PNG bytes, scene, source SHA, application version, profile and geometry.
Host-generated recaptures with different PNG hashes cannot replace original
sidecars merely because the source-code SHA matches. The post-merge
introducing commit must be derived from actual Git history, not stored
self-referentially in this manifest or supplied as an assumed future SHA.
