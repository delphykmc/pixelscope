from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

import numpy as np
from numpy.typing import NDArray

from pixelscope.core.display_transform import DisplayTransform, to_display_uint8
from pixelscope.core.spatial_sampling import SamplingSemantics, SpatialSampling

if TYPE_CHECKING:
    from pixelscope.core.yuv import NativeYuvFrame


@dataclass(frozen=True)
class ImageSampleLookup:
    """One reference-coordinate inspection result for an image document."""

    reference_xy: tuple[int, int]
    sample_xy: tuple[int, int] | None
    sample_reference_xy: tuple[int, int] | None
    value: int | float | tuple[int | float, ...] | None
    sampling_semantics: SamplingSemantics
    channel: str | None = None

    @property
    def semantics(self) -> SamplingSemantics:
        """Short alias suitable for status/presentation callers."""

        return self.sampling_semantics

    @property
    def actual_sample_reference_site(self) -> tuple[int, int] | None:
        """The physical lattice site (or cell origin) of ``sample_xy``."""

        return self.sample_reference_xy

    @property
    def sample_coordinate(self) -> tuple[int, int] | None:
        """Alias that makes the native-coordinate space explicit."""

        return self.sample_xy

    @property
    def actual_cfa_site(self) -> tuple[int, int] | None:
        """Alias for callers that specifically render point-lattice inspection."""

        return self.sample_reference_xy


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
    spatial_sampling: SpatialSampling | None = None
    sample_channel: str | None = None
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

    def __post_init__(self) -> None:
        """Attach default identity sampling without altering native source ownership."""

        if self.source is None:
            if self.spatial_sampling is not None:
                raise ValueError("spatial sampling requires a native source array")
            return
        if self.source.ndim not in (2, 3):
            raise ValueError("images must be HxW or HxWxC")
        source_shape = (int(self.source.shape[0]), int(self.source.shape[1]))
        sampling = self.spatial_sampling or SpatialSampling.identity(source_shape)
        if sampling.sample_shape != self.source.shape[:2]:
            raise ValueError(
                "spatial sampling sample_shape must match the native source image shape"
            )
        self.spatial_sampling = sampling

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
        spatial_sampling: SpatialSampling | None = None,
        sample_channel: str | None = None,
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
            spatial_sampling=spatial_sampling,
            sample_channel=sample_channel,
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
            spatial_sampling=SpatialSampling.identity(frame.shape),
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
    def reference_shape(self) -> tuple[int, int]:
        """Reference-space HxW interaction extent; ``shape`` remains native."""

        if self.spatial_sampling is not None:
            return self.spatial_sampling.reference_shape
        if self.source is None:
            return 0, 0
        return int(self.source.shape[0]), int(self.source.shape[1])

    @property
    def native_nbytes(self) -> int:
        if self.yuv_frame is not None:
            return self.yuv_frame.native_nbytes
        return 0 if self.source is None else int(self.source.nbytes)

    def pixel_at(self, x: int, y: int) -> int | float | tuple[int | float, ...] | None:
        """Return one native-local sample; reference mapping is deliberately separate."""

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

    def sample_lookup_at_reference(self, x: int, y: int) -> ImageSampleLookup | None:
        """Resolve a reference coordinate without changing the native ``pixel_at`` API."""

        sampling = self.spatial_sampling
        if sampling is None:
            return None
        reference_rows, reference_columns = sampling.reference_shape
        if x < 0 or y < 0 or x >= reference_columns or y >= reference_rows:
            return None
        sample_xy = sampling.reference_to_sample(x, y)
        sample_site = None if sample_xy is None else sampling.sample_reference_site(*sample_xy)
        value = None if sample_xy is None else self.pixel_at(*sample_xy)
        return ImageSampleLookup(
            reference_xy=(x, y),
            sample_xy=sample_xy,
            sample_reference_xy=sample_site,
            value=value,
            sampling_semantics=sampling.sampling_semantics,
            channel=self.sample_channel,
        )

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
        self.spatial_sampling = replacement.spatial_sampling
        self.sample_channel = None
        self.preview = replacement.preview
        self.encoded_source_sha256 = None
        self.generation += 1
        self.statistics_cache.clear()
        self.histogram_cache.clear()
        self.loading_state = "ready"
        self.error_state = None
