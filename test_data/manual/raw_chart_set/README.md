# PixelScope synthetic RAW chart set

This folder replaces `manual/bit_depth_variations` with a format-oriented RAW
validation database. Every `.raw` file has a same-stem `.json` RawProfile
sidecar using the current storage schema.

## GRAY fixtures

- 8-bit unpacked `uint8`
- 10/12/14-bit unpacked `uint16`, little-endian, LSB aligned
- 16-bit unpacked `uint16`, little-endian

## RGGB Bayer fixtures

- 10-bit unpacked `uint16`, little-endian, LSB aligned
- 12-bit unpacked `uint16`, little-endian, MSB aligned
- MIPI RAW10: 4 pixels / 5 bytes
- MIPI RAW12: 2 pixels / 3 bytes, width aligned to 4 pixels
- MIPI RAW14: 4 pixels / 7 bytes

All files are 1920 x 1080. Packed profiles do not use a container, byte order,
or bit-alignment option because those details are defined by the storage format.
The Bayer files can be regenerated with:

    python scripts/generate_raw_chart_bayer_fixtures.py

`manifest.json` records profile names, expected value ranges, row strides, and
SHA-256 hashes. Update it whenever a versioned fixture changes.
