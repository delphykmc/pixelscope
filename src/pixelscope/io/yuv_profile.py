from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, root_validator, validator

from pixelscope.core.yuv import YuvLayout


class YuvProfile(BaseModel):
    """Explicit tightly-packed 8-bit semi-planar YUV interpretation for WP-C1."""

    name: str = "native_yuv"
    width: int
    height: int
    channel_layout: YuvLayout
    bit_depth: Literal[8] = 8
    plane_order: Literal["Y+UV"] = "Y+UV"
    chroma_order: Literal["UV"] = "UV"
    color_matrix: Literal["BT.601"] = "BT.601"
    color_range: Literal["Full"] = "Full"

    class Config:
        validate_assignment = True
        extra = "forbid"

    @validator("width", "height")
    def positive_dimension(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("YUV dimensions must be greater than zero")
        return value

    @root_validator
    def validate_subsampling_geometry(cls, values: dict[str, object]) -> dict[str, object]:
        width = values.get("width")
        height = values.get("height")
        layout = values.get("channel_layout")
        if isinstance(width, int) and layout in ("YUV422", "YUV420") and width % 2:
            raise ValueError(f"{layout} width must be even")
        if isinstance(height, int) and layout == "YUV420" and height % 2:
            raise ValueError("YUV420 height must be even")
        return values

    @property
    def expected_file_size(self) -> int:
        luma = self.width * self.height
        if self.channel_layout == "YUV444":
            chroma = luma * 2
        elif self.channel_layout == "YUV422":
            chroma = luma
        else:
            chroma = luma // 2
        return luma + chroma

    @classmethod
    def load_json(cls, path: str | Path) -> YuvProfile:
        return cls.parse_raw(Path(path).read_text(encoding="utf-8"))

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(self.json(indent=2), encoding="utf-8")
