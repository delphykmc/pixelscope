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

FHD GRAY and RGGB RAW fixtures covering unpacked 8/10/12/14/16-bit storage,
16-bit LSB/MSB alignment, and MIPI RAW10/12/14 packing. Each RAW file has a
same-stem profile and is indexed by `manifest.json`.

## `manual/uhd_chart_set/`

4K reference/degraded PNG images, an unpacked RGGB10 RAW frame and its JSON
profile, a Bayer preview, expected metrics, and SHA-256 manifests. Use this set
for 4K loading, RAW interpretation, statistics, Difference, ROI, and display
responsiveness checks.

The manual datasets are intentionally versioned. Do not replace or recompress
their images without updating the corresponding manifest and expected metrics.
