from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.display_transform import DisplayTransform, to_display_uint8

if TYPE_CHECKING:
    from pixelscope.core.yuv import NativeYuvFrame


@dataclass
class ImageDocument:
    """Owns source image semantics and derived, replaceable display/cache data."""

    source_path: Path | None
    display_name: str
    source: NDArray[np.generic] | None
    channel_layout: str
    bit_depth: int
    raw_profile: Any | None = None
    yuv_frame: NativeYuvFrame | None = None
    display_transform: DisplayTransform = field(default_factory=DisplayTransform)
    document_id: str = field(default_factory=lambda: str(uuid4()))
    preview: NDArray[np.uint8] | None = None
    encoded_source_sha256: str | None = field(default=None, compare=False)
    statistics_cache: dict[tuple[Any, ...], Any] = field(default_factory=dict)
    histogram_cache: dict[tuple[Any, ...], Any] = field(default_factory=dict)
    evaluation_results: list[Any] = field(default_factory=list)
    loading_state: str = "ready"
    error_state: str | None = None
    generation: int = 0

    @classmethod
    def from_array(
        cls,
        source: NDArray[np.generic],
        display_name: str,
        source_path: Path | None = None,
        channel_layout: str | None = None,
        bit_depth: int | None = None,
        raw_profile: Any | None = None,
        display_transform: DisplayTransform | None = None,
        prepared_preview: NDArray[np.uint8] | None = None,
        encoded_source_sha256: str | None = None,
    ) -> ImageDocument:
        if source.ndim not in (2, 3):
            raise ValueError("images must be HxW or HxWxC")
        if not np.issubdtype(source.dtype, np.number):
            raise TypeError("image source must use a numeric dtype")
        if source.ndim == 3 and source.shape[2] not in (3, 4):
            raise ValueError("color images must contain 3 (RGB) or 4 (RGBA) channels")
        if source.size == 0:
            raise ValueError("images must not be empty")
        array = np.ascontiguousarray(source) if not source.flags.c_contiguous else source
        layout = channel_layout or ("GRAY" if array.ndim == 2 else "RGB")
        depth = bit_depth or (array.dtype.itemsize * 8)
        transform = display_transform or DisplayTransform()
        if prepared_preview is not None and prepared_preview.shape[:2] != array.shape[:2]:
            raise ValueError("prepared preview dimensions must match the source image")
        preview = (
            np.ascontiguousarray(prepared_preview)
            if prepared_preview is not None
            else to_display_uint8(array, transform)
        )
        return cls(
            source_path=source_path,
            display_name=display_name,
            source=array,
            channel_layout=layout,
            bit_depth=depth,
            raw_profile=raw_profile,
            display_transform=transform,
            preview=preview,
            encoded_source_sha256=encoded_source_sha256,
        )

    @classmethod
    def from_yuv(
        cls,
        frame: NativeYuvFrame,
        display_name: str,
        source_path: Path | None = None,
        raw_profile: Any | None = None,
    ) -> ImageDocument:
        """Create a YUV document whose frame planes, not RGB preview, are authority."""

        from pixelscope.core.yuv import bt601_full_rgb_preview

        preview = bt601_full_rgb_preview(frame)
        return cls(
            source_path=source_path,
            display_name=display_name,
            # `source` remains a zero-copy luma alias for the established loaded/
            # geometry lifecycle. All YUV-aware numerical paths use `yuv_frame`.
            source=frame.y,
            channel_layout=frame.layout,
            bit_depth=8,
            raw_profile=raw_profile,
            yuv_frame=frame,
            display_transform=DisplayTransform(display_low=0.0, display_high=255.0),
            preview=preview,
        )

    @classmethod
    def error_document(
        cls, display_name: str, message: str, path: Path | None = None
    ) -> ImageDocument:
        return cls(
            source_path=path,
            display_name=display_name,
            source=None,
            channel_layout="UNKNOWN",
            bit_depth=0,
            loading_state="error",
            error_state=message,
        )

    @classmethod
    def pending_document(cls, path: Path) -> ImageDocument:
        """Create a lightweight list entry whose pixels will be decoded on demand."""

        return cls(
            source_path=path,
            display_name=path.name,
            source=None,
            channel_layout="UNKNOWN",
            bit_depth=0,
            loading_state="pending",
        )

    @property
    def original_dtype(self) -> np.dtype[Any] | None:
        return None if self.source is None else self.source.dtype

    @property
    def shape(self) -> tuple[int, ...]:
        return () if self.source is None else self.source.shape

    @property
    def native_nbytes(self) -> int:
        if self.yuv_frame is not None:
            return self.yuv_frame.native_nbytes
        return 0 if self.source is None else int(self.source.nbytes)

    def pixel_at(self, x: int, y: int) -> int | float | tuple[int | float, ...] | None:
        if self.yuv_frame is not None:
            try:
                return self.yuv_frame.pixel_at(x, y)
            except IndexError:
                return None
        if self.source is None or x < 0 or y < 0:
            return None
        height, width = self.source.shape[:2]
        if x >= width or y >= height:
            return None
        python_value = np.asarray(self.source[y, x]).tolist()
        if isinstance(python_value, list):
            return cast(tuple[int | float, ...], tuple(python_value))
        return cast(int | float, python_value)

    def replace_source(self, source: NDArray[np.generic]) -> None:
        """Replace data atomically and invalidate all derived caches."""

        replacement = ImageDocument.from_array(
            source=source,
            display_name=self.display_name,
            source_path=self.source_path,
            channel_layout=self.channel_layout,
            bit_depth=self.bit_depth,
            raw_profile=self.raw_profile,
            display_transform=self.display_transform,
        )
        self.source = replacement.source
        self.yuv_frame = None
        self.preview = replacement.preview
        self.encoded_source_sha256 = None
        self.generation += 1
        self.statistics_cache.clear()
        self.histogram_cache.clear()
        self.loading_state = "ready"
        self.error_state = None
