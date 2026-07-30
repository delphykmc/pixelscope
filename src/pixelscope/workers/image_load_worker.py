from __future__ import annotations

from pathlib import Path

from pixelscope.core.bayer import render_bayer_preview
from pixelscope.core.display_transform import DisplayTransform
from pixelscope.core.image_document import ImageDocument
from pixelscope.io.image_reader import read_image
from pixelscope.io.raw_profile import RawProfile
from pixelscope.io.raw_reader import read_raw
from pixelscope.workers.task_worker import TaskWorker


class ImageLoadWorker(TaskWorker):
    """Background image/RAW decoder with normal TaskWorker lifecycle signals."""

    def __init__(self, path: str | Path, raw_profile: RawProfile | None = None) -> None:
        source_path = Path(path)

        def load() -> ImageDocument:
            if raw_profile is None:
                return read_image(source_path)
            source = read_raw(source_path, raw_profile)
            transform = DisplayTransform(
                black_level=raw_profile.display_black_level,
                white_level=raw_profile.white_level,
            )
            return ImageDocument.from_array(
                source,
                display_name=source_path.name,
                source_path=source_path,
                channel_layout=raw_profile.channel_layout,
                bit_depth=raw_profile.bit_depth,
                raw_profile=raw_profile,
                display_transform=transform,
                prepared_preview=(
                    render_bayer_preview(source, transform)
                    if raw_profile.channel_layout == "BAYER"
                    else None
                ),
            )

        super().__init__(load)
