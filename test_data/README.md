# PixelScope test data

This directory separates reproducible development fixtures from the larger
manual validation database.

## `generated/`

Small deterministic fixtures created by `scripts/generate_test_images.py`.
The directory is ignored by Git because every file can be regenerated.

## `manual/fhd_chart_set/`

Thirty 1920×1080 JPEG charts arranged as three naturally paired folders:
`base`, `variation_noise`, and `variation_tone`. Use this set to validate
folder registration, Page Up/Page Down pair navigation, and multi-view
comparison. The matching filename at each natural-sort index forms a pair.

## `manual/raw_chart_set/`

FHD GRAY and RGGB RAW fixtures covering unpacked `uint8`/`uint16`, LSB/MSB
alignment, and MIPI RAW10/12/14 storage. Filenames are prefixed so natural
sorting shows all GRAY fixtures first and then the Bayer variants grouped by
bit depth and storage format.

The Bayer fixtures are sampled from one true RGB chart before quantization and
serialization. Reference PNGs are stored under `references/` so they do not
mix with RAW files during normal folder registration. Use this set to validate
RAW profiles, packing, alignment, stride, Bayer channel splitting, and preview
interpretation.

## `manual/uhd_chart_set/`

4K reference/degraded PNG images, an unpacked RGGB10 RAW frame and its JSON
profile, a Bayer preview, expected metrics, and SHA-256 manifests. Use this set
for 4K loading, RAW interpretation, statistics, Difference, ROI, and display
responsiveness checks.

The manual datasets are intentionally versioned. Do not replace or recompress
their images without updating the corresponding manifest and expected metrics.
