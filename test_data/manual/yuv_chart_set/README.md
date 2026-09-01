# PixelScope synthetic YUV manual fixture set

This directory is a small, deterministic WP-C1 manual-validation database.

## Native YUV fixtures

`01`-`04` intentionally have **no JSON sidecar**. Opening them exercises the
new `YUV profile` dialog instead of bypassing it with a YUV profile file.

Use Width `16`, Height `12`, and the interpretation in the filename. The fixed
contract is 8-bit, Y first + interleaved UV, UV order, BT.601 Full, tightly packed.

| File | Expected bytes | Native Y/U/V shapes | Full-frame samples Y/U/V |
| --- | ---: | --- | --- |
| `01_yuv444_16x12.yuv` | 576 | 16x12 / 16x12 / 16x12 | 192 / 192 / 192 |
| `02_yuv422_16x12.yuv` | 384 | 16x12 / 8x12 / 8x12 | 192 / 96 / 96 |
| `03_yuv420_16x12.yuv` | 288 | 16x12 / 8x6 / 8x6 | 192 / 48 / 48 |
| `04_yuv420_variant_16x12.yuv` | 288 | 16x12 / 8x6 / 8x6 | 192 / 48 / 48 |

The native pattern is deterministic:

- `Y(x,y) = 32 + 8*x + 4*y`
- `U(cx,cy) = 32 + ((17*cx + 11*cy) mod 192)`
- `V(cx,cy) = 224 - ((13*cx + 7*cy) mod 192)`

Chroma coordinates are 444 `(x,y)`, 422 `(x//2,y)`, and 420 `(x//2,y//2)`.
Useful cursor checks:

| coordinate | 444 Y,U,V | 422 Y,U,V | 420 Y,U,V |
| --- | --- | --- | --- |
| `(0,0)` | 32,32,224 | 32,32,224 | 32,32,224 |
| `(1,0)` | 40,49,211 | 40,32,224 | 40,32,224 |
| `(2,0)` | 48,66,198 | 48,49,211 | 48,49,211 |
| `(0,1)` | 36,43,217 | 36,43,217 | 36,32,224 |
| `(0,2)` | 40,54,210 | 40,54,210 | 40,43,217 |
| `(3,3)` | 68,116,164 | 68,82,190 | 68,60,204 |

`04` is `03` with exact native deltas `ΔY=+10`, `ΔU=+8`, `ΔV=-8`.
Use the pair for two-image native cursor/delta validation.

## ROI / Histogram / Line

For YUV420 ROI `(x=1,y=1,w=3,h=3)`, expected sample counts are Y=9, U=4, V=4.

For horizontal line `(0,0) -> (15,0)`:

- 444: Y/U/V positions = 0..15
- 422: Y = 0..15; U/V = 0,2,4,...,14
- 420: Y = 0..15; U/V = 0,2,4,...,14

For vertical YUV420 line `(0,0) -> (0,11)`, U/V positions are 0,2,4,6,8,10.

## Split

Expected display plane sizes are:

- 444: Y 16x12, U 16x12, V 16x12
- 422: Y 16x12, U 8x12, V 8x12
- 420: Y 16x12, U 8x6, V 8x6

U/V split views should be grayscale native-plane views, not false color.

## `.yuv + .imgprops` fallback

`05_legacy_bayer12_imgprops_16x12.yuv` is deliberately **RAW Bayer data with a
`.yuv` extension**, paired with a same-stem `.imgprops`. It validates the WP-B
fallback/precedence contract: it must use the existing Generic RAW/Bayer path,
not the native YUV dialog.

Expected interpretation from `.imgprops`: 16x12, BAYER12 RGGB, unpacked uint16,
little-endian, LSB aligned, minimum stride 32, pedestal/black level 256.

## Negative fixtures

`negative/` is outside normal root-folder registration. Select Width=16,
Height=12, YUV420:

- `yuv420_short_16x12.yuv`: 287 bytes -> reject (expected 288)
- `yuv420_long_16x12.yuv`: 289 bytes -> reject (expected 288)

Geometry rejection can be checked with any fixture by entering odd width for
YUV422, or odd width/height for YUV420.

## Reference previews

`references/` contains deterministic BT.601 Full RGB PNG references for `01`-`04`.
These are viewer references only. Pixel/Statistics/Histogram/Line/Split must still
use native Y/U/V values.

## Regeneration

From repository root:

    python scripts/generate_yuv_manual_fixtures.py

The generator writes `test_data/manual/yuv_chart_set` and `manifest.json`.
