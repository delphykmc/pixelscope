from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.bayer import bayer_channel_positions, split_bayer_channels
from pixelscope.core.display_transform import to_display_uint8
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.spatial_sampling import SpatialSampling


def split_document_channels(document: ImageDocument) -> list[ImageDocument]:
    """Build transient visual documents for RGB, Bayer, or native YUV subchannels."""

    if document.yuv_frame is not None:
        documents: list[ImageDocument] = []
        for name, yuv_channel in zip(("Y", "U", "V"), document.yuv_frame.planes, strict=True):
            preview = _gray_preview(yuv_channel)
            documents.append(_yuv_channel_document(document, name, yuv_channel, preview))
        return documents

    source = document.source
    if source is None:
        return []
    if document.channel_layout in ("RGB", "RGBA") and source.ndim == 3:
        names = ("R", "G", "B")
        documents = []
        for channel_index, name in enumerate(names):
            source_channel = source[..., channel_index]
            display = to_display_uint8(source_channel, document.display_transform)
            preview = np.zeros((*display.shape, 3), dtype=np.uint8)
            preview[..., channel_index] = display
            documents.append(_channel_document(document, name, source_channel, preview))
        return documents
    pattern = getattr(document.raw_profile, "bayer_pattern", None)
    if document.channel_layout == "BAYER" and source.ndim == 2 and isinstance(pattern, str):
        documents = []
        positions = bayer_channel_positions(pattern)
        for name, bayer_channel in split_bayer_channels(source, pattern):
            display = to_display_uint8(bayer_channel, document.display_transform)
            preview = np.zeros((*display.shape, 3), dtype=np.uint8)
            if name == "R":
                preview[..., 0] = display
            elif name == "B":
                preview[..., 2] = display
            else:
                preview[..., 1] = display
            row_phase, column_phase = positions[name]
            documents.append(
                _channel_document(
                    document,
                    name,
                    bayer_channel,
                    preview,
                    spatial_sampling=SpatialSampling.point_lattice(
                        document.reference_shape,
                        (int(bayer_channel.shape[0]), int(bayer_channel.shape[1])),
                        row_step=2,
                        column_step=2,
                        row_phase=row_phase,
                        column_phase=column_phase,
                    ),
                )
            )
        return documents
    return []


def _channel_document(
    source_document: ImageDocument,
    channel_name: str,
    channel: NDArray[np.generic],
    preview: NDArray[np.uint8],
    *,
    spatial_sampling: SpatialSampling | None = None,
) -> ImageDocument:
    """Build a split document while preserving safe native ndarray views."""

    document = ImageDocument(
        source_path=source_document.source_path,
        display_name=f"{source_document.display_name} · {channel_name}",
        source=channel,
        channel_layout=f"CHANNEL_{channel_name}",
        bit_depth=source_document.bit_depth,
        raw_profile=source_document.raw_profile,
        spatial_sampling=spatial_sampling,
        sample_channel=channel_name,
        display_transform=source_document.display_transform,
        preview=np.ascontiguousarray(preview),
        loading_state="ready",
        generation=source_document.generation,
    )
    # Split views are transient, but their identity must be stable and traceable
    # to the source document so MainWindow can preserve an explicit Primary
    # channel across rerenders without guessing from display names or UUIDs.
    document.document_id = f"{source_document.document_id}:split:{channel_name}"
    return document


def _yuv_channel_document(
    source_document: ImageDocument,
    channel_name: str,
    channel: NDArray[np.generic],
    preview: NDArray[np.uint8],
) -> ImageDocument:
    """Keep one native-resolution YUV plane view without forcing a contiguous copy."""

    reference_shape = source_document.reference_shape
    frame = source_document.yuv_frame
    assert frame is not None
    channel_shape = (int(channel.shape[0]), int(channel.shape[1]))
    if channel_name == "Y":
        sampling = SpatialSampling.identity(channel_shape)
    else:
        column_step, row_step = frame.chroma_scale
        sampling = SpatialSampling.cell_footprint(
            reference_shape,
            channel_shape,
            row_step=row_step,
            column_step=column_step,
        )
    document = ImageDocument(
        source_path=source_document.source_path,
        display_name=f"{source_document.display_name} · {channel_name}",
        source=channel,
        channel_layout=f"CHANNEL_{channel_name}",
        bit_depth=source_document.bit_depth,
        raw_profile=source_document.raw_profile,
        spatial_sampling=sampling,
        sample_channel=channel_name,
        display_transform=source_document.display_transform,
        preview=np.ascontiguousarray(preview),
        loading_state="ready",
        generation=source_document.generation,
    )
    document.document_id = f"{source_document.document_id}:split:{channel_name}"
    return document


def _gray_preview(channel: NDArray[np.generic]) -> NDArray[np.uint8]:
    """Build a native-grid gray RGB preview without reference-grid expansion."""

    preview = np.empty((*channel.shape, 3), dtype=np.uint8)
    preview[..., 0] = channel
    preview[..., 1] = channel
    preview[..., 2] = channel
    return preview
