from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, root_validator, validator

from pixelscope.io.raw_format import (
    BitAlignment,
    ContainerDType,
    Endianness,
    StorageFormat,
    container_bit_count,
    container_byte_count,
    minimum_row_bytes,
    storage_format_spec,
)


class RawProfile(BaseModel):
    """Validated byte-layout and signal interpretation for one RAW image."""

    name: str
    width: int
    height: int
    stride_bytes: int
    offset_bytes: int = 0
    storage_format: StorageFormat = "unpacked"
    container_dtype: ContainerDType | None = "uint16"
    endianness: Endianness | None = "little"
    bit_depth: int
    bit_alignment: BitAlignment | None = "lsb"
    channel_layout: Literal["GRAY", "BAYER"] = "GRAY"
    bayer_pattern: Literal["RGGB", "GRBG", "GBRG", "BGGR"] | None = None
    black_level: int | tuple[int, int, int, int] = 0
    white_level: int

    class Config:
        validate_assignment = True
        extra = "ignore"

    @root_validator(pre=True)
    def migrate_legacy_storage_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Read old dtype/packing profiles without serializing the old schema."""

        migrated = dict(values)
        legacy_packing = migrated.get("packing")
        legacy_dtype = migrated.get("dtype")

        if "storage_format" not in migrated:
            if legacy_packing in ("unpacked_u8", "unpacked_u16"):
                migrated["storage_format"] = "unpacked"
            elif legacy_packing in ("mipi_raw10", "mipi_raw12", "mipi_raw14"):
                migrated["storage_format"] = legacy_packing

        if "container_dtype" not in migrated:
            if legacy_dtype in ("uint8", "uint16"):
                migrated["container_dtype"] = legacy_dtype
            elif legacy_packing == "unpacked_u8":
                migrated["container_dtype"] = "uint8"
            elif legacy_packing == "unpacked_u16":
                migrated["container_dtype"] = "uint16"

        storage_format = migrated.get("storage_format", "unpacked")
        if storage_format != "unpacked":
            migrated.setdefault("container_dtype", None)
            migrated.setdefault("endianness", None)
            migrated.setdefault("bit_alignment", None)
        elif "bit_alignment" not in migrated:
            container_dtype = migrated.get("container_dtype")
            bit_depth = migrated.get("bit_depth")
            if container_dtype in ("uint8", "uint16") and isinstance(bit_depth, int):
                migrated["bit_alignment"] = (
                    "lsb" if bit_depth < container_bit_count(container_dtype) else None
                )

        return migrated

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
        levels = (value,) if isinstance(value, int) else value
        if len(levels) not in (1, 4) or any(level < 0 for level in levels):
            raise ValueError("black_level must be a non-negative scalar or four Bayer levels")
        return value

    @root_validator
    def validate_storage_and_signal(cls, values: dict[str, Any]) -> dict[str, Any]:
        storage_format = values.get("storage_format")
        width = values.get("width")
        height = values.get("height")
        stride = values.get("stride_bytes")
        bit_depth = values.get("bit_depth")
        container_dtype = values.get("container_dtype")

        if storage_format is None:
            return values
        spec = storage_format_spec(storage_format)

        if spec.is_packed:
            if bit_depth != spec.fixed_bit_depth:
                raise ValueError(f"{spec.label} requires bit_depth={spec.fixed_bit_depth}")
            values["container_dtype"] = None
            values["endianness"] = None
            values["bit_alignment"] = None
            if isinstance(width, int) and width % spec.width_alignment:
                raise ValueError(
                    f"{spec.label} width must be a multiple of " f"{spec.width_alignment} pixels"
                )
            if isinstance(height, int) and height % 2:
                raise ValueError(f"{spec.label} height must be even")
        else:
            if container_dtype not in ("uint8", "uint16"):
                raise ValueError("Unpacked RAW requires container_dtype")
            container_bits = container_bit_count(container_dtype)
            if isinstance(bit_depth, int) and bit_depth > container_bits:
                raise ValueError("bit_depth exceeds the selected container")
            if container_dtype == "uint8":
                values["endianness"] = None
            elif values.get("endianness") is None:
                values["endianness"] = "little"
            if isinstance(bit_depth, int) and bit_depth < container_bits:
                if values.get("bit_alignment") not in ("lsb", "msb"):
                    values["bit_alignment"] = "lsb"
            else:
                values["bit_alignment"] = None

        if isinstance(width, int) and isinstance(stride, int):
            minimum = minimum_row_bytes(width, storage_format, values.get("container_dtype"))
            if stride < minimum:
                raise ValueError("stride_bytes is smaller than one image row")
            if storage_format == "unpacked" and values.get("container_dtype") is not None:
                item_size = container_byte_count(values["container_dtype"])
                if stride % item_size:
                    raise ValueError("stride_bytes must align to the container size")

        black = values.get("black_level", 0)
        white = values.get("white_level")
        black_maximum = max(black) if isinstance(black, tuple) else black
        if isinstance(white, int) and isinstance(black_maximum, int) and white <= black_maximum:
            raise ValueError("white_level must be greater than black_level")
        if isinstance(white, int) and isinstance(bit_depth, int) and white > (1 << bit_depth) - 1:
            raise ValueError("white_level exceeds bit_depth")

        if values.get("channel_layout") == "BAYER" and values.get("bayer_pattern") is None:
            raise ValueError("bayer_pattern is required for BAYER layout")
        return values

    @classmethod
    def load_json(cls, path: str | Path) -> RawProfile:
        return cls.parse_raw(Path(path).read_text(encoding="utf-8"))

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(self.json(indent=2), encoding="utf-8")

    @property
    def minimum_row_bytes(self) -> int:
        return minimum_row_bytes(
            self.width,
            self.storage_format,
            self.container_dtype,
        )

    @property
    def container_bits(self) -> int | None:
        if self.container_dtype is None:
            return None
        return container_bit_count(self.container_dtype)

    @property
    def dtype(self) -> Literal["uint8", "uint16"]:
        """Compatibility view for code that still asks for a decoded dtype."""

        return self.container_dtype or "uint16"

    @property
    def packing(self) -> str:
        """Compatibility view for old code and in-memory comparisons."""

        if self.storage_format == "unpacked":
            return "unpacked_u8" if self.container_dtype == "uint8" else "unpacked_u16"
        return self.storage_format
