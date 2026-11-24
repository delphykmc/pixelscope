# Supported Formats

This table describes the current local registration/input surface.

| Extension | Local interpretation |
|---|---|
| `.png` | Standard image |
| `.bmp` | Standard image |
| `.jpg`, `.jpeg` | Standard image |
| `.raw` | RAW-like input; profile/metadata may be required |
| `.data` | RAW-like input; profile/metadata may be required |
| `.yuv` | Explicit native YUV **or** Generic RAW interpretation |

Folder discovery and direct file input use the same supported extension set.

## RAW storage formats

RAW supports unpacked `uint8`, unpacked `uint16`, generic 1-16-bit packed streams with MSB/LSB-first bit order and per-row stride, and MIPI RAW10/12/14 with the validated layout rules described in the [RAW Guide](../formats/raw.md).

## Native YUV formats

Native YUV supports current 8-bit YUV444, YUV422, and YUV420 semantics described in the [YUV Guide](../formats/yuv.md).

## Optional IQA

Core has no IQA implementation. The separate Reference package uses mock results; real Enterprise submission formats and conversion behavior are downstream-owned. Local RAW/YUV viewing support does not establish an IQA submission contract.
