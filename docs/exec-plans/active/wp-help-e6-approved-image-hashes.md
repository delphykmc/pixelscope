# WP-Help-E6 — exact approved screenshot byte identities

**Provisional hash listing, not a substitute for the owner's explicit exact-byte attestation.**

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

**Owner evidence gate:** the owner should confirm that these specific 14
committed files/hashes, not merely the screenshot *names*, are the unchanged
images viewed and approved in the temporary local User Guide. Record that
attestation as a new external owner PR comment referencing this hash listing
and the exact promotion commit. Do not interpret a maintainer-generated list
as the owner's attestation; use the new owner's comment as the approval
reference after that explicit confirmation. Future image-byte modifications
require new visual approval.

**Capture provenance is a different gate.** Local candidate sidecars from the
original `631779bb91278e846f39e376dd1bef8210df1e5c` capture must independently agree with the matching
PNG bytes, scene, source SHA, application version, profile and geometry.
Host-generated recaptures with different PNG hashes cannot replace original
sidecars merely because the source-code SHA matches. The post-merge
introducing commit must be derived from actual Git history, not stored
self-referentially in this manifest or supplied as an assumed future SHA.
