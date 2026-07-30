from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, validator


class RawProfile(BaseModel):
    """Validated interpretation of an unpacked RAW byte stream."""

    name: str
    width: int
    height: int
    dtype: Literal["uint8", "uint16"]
    stride_bytes: int
    offset_bytes: int = 0
    endianness: Literal["little", "big"] = "little"
    bit_depth: int
    packing: Literal[
        "unpacked_u8",
        "unpacked_u16",
        "mipi_raw10",
        "mipi_raw12",
        "mipi_raw14",
    ]
    channel_layout: Literal["GRAY", "BAYER"] = "GRAY"
    bayer_pattern: Literal["RGGB", "GRBG", "GBRG", "BGGR"] | None = None
    black_level: int | tuple[int, int, int, int] = 0
    white_level: int

    class Config:
        validate_assignment = True

    @validator("width", "height", "stride_bytes", "bit_depth", "white_level")
    def positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("value must be greater than zero")
        return value

    @validator("offset_bytes")
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("value must not be negative")
        return value

    @validator("channel_layout", pre=True)
    def normalize_channel_layout(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @validator("black_level")
    def validate_black_level(
        cls, value: int | tuple[int, int, int, int]
    ) -> int | tuple[int, int, int, int]:
        values = (value,) if isinstance(value, int) else value
        if len(values) not in (1, 4) or any(level < 0 for level in values):
            raise ValueError("black_level must be a non-negative scalar or four Bayer levels")
        return value

    @validator("packing")
    def packing_matches_dtype(cls, value: str, values: dict[str, object]) -> str:
        dtype = values.get("dtype")
        if value == "unpacked_u8" and dtype != "uint8":
            raise ValueError("unpacked_u8 requires dtype=uint8")
        if value == "unpacked_u16" and dtype != "uint16":
            raise ValueError("unpacked_u16 requires dtype=uint16")
        return value

    @validator("stride_bytes")
    def stride_contains_row(cls, value: int, values: dict[str, object]) -> int:
        width = values.get("width")
        if isinstance(width, int):
            item_size = 1 if values.get("dtype") == "uint8" else 2
            if value < width * item_size:
                raise ValueError("stride_bytes is smaller than one image row")
            if value % item_size:
                raise ValueError("stride_bytes must align to the sample size")
        return value

    @validator("white_level")
    def levels_and_depth(cls, value: int, values: dict[str, object]) -> int:
        black = values.get("black_level", 0)
        depth = values.get("bit_depth")
        black_maximum = max(black) if isinstance(black, tuple) else black
        if isinstance(black_maximum, int) and value <= black_maximum:
            raise ValueError("white_level must be greater than black_level")
        if isinstance(depth, int) and value > (1 << depth) - 1:
            raise ValueError("white_level exceeds bit_depth")
        return value

    @validator("bayer_pattern", always=True)
    def bayer_pattern_required(cls, value: str | None, values: dict[str, object]) -> str | None:
        if values.get("channel_layout") == "BAYER" and value is None:
            raise ValueError("bayer_pattern is required for BAYER layout")
        return value

    @classmethod
    def load_json(cls, path: str | Path) -> RawProfile:
        return cls.parse_raw(Path(path).read_text(encoding="utf-8"))

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(self.json(indent=2), encoding="utf-8")

    @property
    def display_black_level(self) -> int:
        """Return a scalar black level suitable for the current global preview."""

        if isinstance(self.black_level, tuple):
            return min(self.black_level)
        return self.black_level
