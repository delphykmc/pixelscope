PixelScope synthetic 4K test samples
====================================

Files
-----
1. scene_reference_4k.png
   - 3840 x 2160, lossless PNG
   - Crisp reference scene with gradients, fine texture, slanted edges,
     checkerboards, line-frequency targets, small text and smooth regions.

2. scene_degraded_4k.png
   - Same geometry and exact resolution as the reference.
   - Degradation: 2x down/up sampling, Gaussian blur, channel noise,
     slight contrast loss and JPEG artifacts.
   - Stored as PNG so the degraded pixel values remain deterministic.

3. scene_reference_4k_rggb10_u16le.raw
   - 3840 x 2160 Bayer RAW.
   - RGGB pattern.
   - Effective bit depth: 10 bits.
   - Storage: unpacked little-endian uint16.
   - Pixel values occupy the lower 10 bits.
   - Black level: 64
   - White level: 1023
   - Row stride: 7680 bytes.
   - File size: 16588800 bytes.

4. scene_reference_4k_rggb10_u16le.json
   - RAW profile for PixelScope.

5. scene_reference_4k_rggb10_preview.png
   - Demosaiced preview for checking Bayer interpretation.

6. expected_metrics.json
   - Deterministic comparison statistics.
   - RGB MSE: 199.552839
   - RGB PSNR: 25.1302 dB
   - Mean absolute difference: 6.715695
   - Maximum absolute difference: 170

7. manifest_sha256.json
   - File sizes and SHA-256 hashes.

Recommended PixelScope RAW settings
-----------------------------------
Width: 3840
Height: 2160
Stride bytes: 7680
Offset bytes: 0
Dtype: uint16
Endian: little
Bit depth: 10
Packing: unpacked_u16
Bayer pattern: RGGB
Black level: 64
White level: 1023
