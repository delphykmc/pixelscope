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

RAW supports unpacked `uint8`, unpacked `uint16`, and MIPI RAW10/12/14 with the validated dimension/stride/alignment rules described in the [RAW Guide](../formats/raw.md).

## Native YUV formats

Native YUV supports current 8-bit YUV444, YUV422, and YUV420 semantics described in the [YUV Guide](../formats/yuv.md).

## Remote IQA submission

Remote IQA submission is a separate contract from local viewing. The current submission input surface is limited to `.png`, `.bmp`, `.jpg`, and `.jpeg`; local RAW/YUV support does not imply an automatic remote conversion path.
