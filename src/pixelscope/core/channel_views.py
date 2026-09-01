from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.bayer import split_bayer_channels
from pixelscope.core.display_transform import to_display_uint8
from pixelscope.core.image_document import ImageDocument


def split_document_channels(document: ImageDocument) -> list[ImageDocument]:
    """Build transient visual documents for RGB, Bayer, or native YUV subchannels."""

    if document.yuv_frame is not None:
        documents: list[ImageDocument] = []
        for name, channel in zip(("Y", "U", "V"), document.yuv_frame.planes, strict=True):
            preview = np.repeat(channel[..., None], 3, axis=2)
            documents.append(_channel_document(document, name, channel, preview))
        return documents

    source = document.source
    if source is None:
        return []
    if document.channel_layout in ("RGB", "RGBA") and source.ndim == 3:
        names = ("R", "G", "B")
        documents = []
        for channel_index, name in enumerate(names):
            channel = source[..., channel_index]
            display = to_display_uint8(channel, document.display_transform)
            preview = np.zeros((*display.shape, 3), dtype=np.uint8)
            preview[..., channel_index] = display
            documents.append(_channel_document(document, name, channel, preview))
        return documents
    pattern = getattr(document.raw_profile, "bayer_pattern", None)
    if document.channel_layout == "BAYER" and source.ndim == 2 and isinstance(pattern, str):
        documents = []
        for name, channel in split_bayer_channels(source, pattern):
            display = to_display_uint8(channel, document.display_transform)
            preview = np.zeros((*display.shape, 3), dtype=np.uint8)
            if name == "R":
                preview[..., 0] = display
            elif name == "B":
                preview[..., 2] = display
            else:
                preview[..., 1] = display
            documents.append(_channel_document(document, name, channel, preview))
        return documents
    return []


def _channel_document(
    source_document: ImageDocument,
    channel_name: str,
    channel: NDArray[np.generic],
    preview: NDArray[np.uint8],
) -> ImageDocument:
    # Split views are presentation objects. Keep the native-resolution plane view as
    # their scalar source and allocate only the RGB grayscale/color preview required
    # by the viewer; no full-resolution YUV chroma authority is synthesized.
    document = ImageDocument(
        source_path=source_document.source_path,
        display_name=f"{source_document.display_name} · {channel_name}",
        source=channel,
        channel_layout=f"CHANNEL_{channel_name}",
        bit_depth=source_document.bit_depth,
        raw_profile=source_document.raw_profile,
        display_transform=source_document.display_transform,
        preview=np.ascontiguousarray(preview),
        loading_state="ready",
        generation=source_document.generation,
    )
    # Split identities must remain stable and traceable to the source document.
    document.document_id = f"{source_document.document_id}:split:{channel_name}"
    return document
