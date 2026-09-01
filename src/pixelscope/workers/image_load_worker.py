from __future__ import annotations

from pathlib import Path

from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.core.raw_display import raw_full_scale, render_raw_preview
from pixelscope.io.image_reader import read_image
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw
from pixelscope.io.yuv_profile import YuvProfile
from pixelscope.io.yuv_reader import read_yuv
from pixelscope.workers.task_worker import TaskWorker


class ImageLoadWorker(TaskWorker):
    """Background image/RAW/YUV decoder with normal TaskWorker lifecycle signals."""

    def __init__(
        self,
        path: str | Path,
        raw_profile: RawProfile | YuvProfile | None = None,
        *,
        require_exact_raw_size: bool = False,
    ) -> None:
        source_path = Path(path)

        def load() -> ImageDocument:
            if raw_profile is None:
                return read_image(source_path)
            if isinstance(raw_profile, YuvProfile):
                frame = read_yuv(source_path, raw_profile)
                return ImageDocument.from_yuv(
                    frame,
                    display_name=source_path.name,
                    source_path=source_path,
                    raw_profile=raw_profile,
                )
            source = read_raw(
                source_path,
                raw_profile,
                require_exact_size=require_exact_raw_size,
            )
            transform = DisplayTransform(
                display_low=0.0,
                display_high=float(raw_full_scale(raw_profile.bit_depth)),
            )
            preview = render_raw_preview(
                source,
                channel_layout=raw_profile.channel_layout,
                bit_depth=raw_profile.bit_depth,
                black_level=raw_profile.black_level,
                bayer_pattern=raw_profile.bayer_pattern,
                gain=1.0,
            )
            return ImageDocument.from_array(
                source,
                display_name=source_path.name,
                source_path=source_path,
                channel_layout=raw_profile.channel_layout,
                bit_depth=raw_profile.bit_depth,
                raw_profile=raw_profile,
                display_transform=transform,
                prepared_preview=preview,
            )

        super().__init__(load)
