# WP-C2 native YUV Difference manual pairs

These tiny deterministic files are supplemental manual-validation fixtures for
WP-C2. Each format has an `a`/`b` pair with identical geometry and subsampling.

Open both files in a pair with Width `16`, Height `12`, 8-bit native YUV,
Y first + interleaved UV, UV order, BT.601 Full, tightly packed.

| Pair | Layout | Bytes/file | Native Y/U/V shapes |
| --- | --- | ---: | --- |
| `yuv444_a_16x12.yuv` / `yuv444_b_16x12.yuv` | YUV444 | 576 | 16x12 / 16x12 / 16x12 |
| `yuv422_a_16x12.yuv` / `yuv422_b_16x12.yuv` | YUV422 | 384 | 16x12 / 8x12 / 8x12 |
| `yuv420_a_16x12.yuv` / `yuv420_b_16x12.yuv` | YUV420 | 288 | 16x12 / 8x6 / 8x6 |

For every format, `b` is derived from `a` with exact native-plane deltas:

- `Y_b = Y_a + 10`
- `U_b = U_a + 8`
- `V_b = V_a - 8`

Therefore the expected full-frame Absolute Difference is constant:

| Channel | Absolute Difference | MAE | MSE | RMSE | Max | Non-zero ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Y | 10 | 10 | 100 | 10 | 10 | 1.0 |
| U | 8 | 8 | 64 | 8 | 8 | 1.0 |
| V | 8 | 8 | 64 | 8 | 8 | 1.0 |

The same constant metrics should remain true for any valid ROI because every
native sample in a plane has the same pairwise delta.

## Recommended WP-C2 checks

1. Calculate Y, U, and V for each same-format pair.
2. Confirm Y is the default channel and there is no combined/All YUV channel.
3. Confirm U/V Difference map dimensions stay native:
   - 444: 16x12
   - 422: 8x12
   - 420: 8x6
4. With Y Difference visible, switch to an uncached U or V channel. The stale
   Y result must disappear until the requested channel result is available.
5. After caching Y/U/V, switch repeatedly between channels and confirm the
   exact cached plane is restored without showing another channel's result.
6. Try mixed pairs (444 vs 422, 422 vs 420, or 444 vs 420). Calculation must
   be rejected rather than resampled or converted.

These files intentionally have no sidecars so opening them exercises the native
YUV interpretation path used by the existing manual fixture set.
