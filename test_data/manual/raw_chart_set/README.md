# PixelScope synthetic RAW chart set

This directory is a format-oriented FHD RAW validation database. Every `.raw`
file has a same-stem `.json` RawProfile sidecar using the current storage
schema.

## Natural-sort order

The numeric prefixes make normal folder registration deterministic:

1. `01_gray_*`: all GRAY fixtures
2. `02_bayer_*`: all Bayer fixtures

Within the Bayer group, equal bit depths place unpacked storage before the MIPI
packed equivalent so they can be compared consecutively.

## GRAY fixtures

- 8-bit unpacked `uint8`
- 10/12/14-bit unpacked `uint16`, little-endian, LSB aligned
- 16-bit unpacked `uint16`, little-endian

## RGGB Bayer fixtures

The main Bayer scene is generated as a true RGB chart and then sampled at RGGB
CFA positions before bit-depth quantization and storage encoding:

    RGB chart -> RGGB sampling -> quantization -> unpacked or MIPI serialization

The set contains:

- 10-bit unpacked `uint16`, little-endian, LSB aligned
- MIPI RAW10: 4 pixels / 5 bytes
- 12-bit unpacked `uint16`, little-endian, MSB aligned
- MIPI RAW12: 2 pixels / 3 bytes
- MIPI RAW14: 4 pixels / 7 bytes

The true RGB source contains color bars, smooth and stepped neutral ramps,
checkerboard, RGB gradients, rings, a slanted edge, and neutral frequency
bands. A future demosaic preview should resemble the RGB source in low-frequency
areas, while high-frequency regions may show interpolation artifacts.

## Reference images

Reference PNGs are kept in `references/` so opening `raw_chart_set` normally
registers only the ten RAW files:

- `references/bayer_reference_rgb.png`: true RGB source before CFA sampling
- `references/bayer_reference_mosaic.png`: normalized RGGB mosaic shown as gray
- `references/bayer_reference_pixelscope.png`: exact current green-tinted preview

The bottom-right 256×256 region is an isolated decoder-coverage patch. Each
code is written to a complete 2×2 RGGB block, keeping that patch CFA-neutral.
It covers every native code at least once in the 10, 12, and 14-bit fixtures.
This patch is for bit-exact decoding checks rather than color-scene fidelity.

Packed profiles have no sample container, byte order, or bit-alignment fields;
those byte-layout rules are defined by the selected MIPI storage format.

## Regeneration

Run from the repository root:

    python scripts/generate_raw_chart_bayer_fixtures.py

The generator replaces the five Bayer RAW files, their profiles, the reference
PNGs, and the Bayer section of `manifest.json`. Existing GRAY metadata is
preserved.

## Validation

The integration test checks:

- natural sorting with GRAY before Bayer
- manifest, SHA-256, profile, stride, shape, and value-range consistency
- exact RAW10 equality between unpacked and MIPI storage
- exact RAW12 equality between MSB-aligned unpacked and MIPI storage
- normalized scene agreement across 10, 12, and 14-bit variants
- RGGB sampling against the true RGB source reference
- full code coverage and CFA neutrality of the isolated patch
- exact agreement between reference PNGs and the current PixelScope preview

Run:

    python -m pytest tests/integration/test_raw_chart_set.py -q
