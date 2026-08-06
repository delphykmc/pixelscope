from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

StorageFormat = Literal[
    "unpacked",
    "mipi_raw10",
    "mipi_raw12",
    "mipi_raw14",
]
ContainerDType = Literal["uint8", "uint16"]
BitAlignment = Literal["lsb", "msb"]
Endianness = Literal["little", "big"]


@dataclass(frozen=True)
class StorageFormatSpec:
    """Static byte-layout rules for one supported RAW storage format."""

    key: StorageFormat
    label: str
    fixed_bit_depth: int | None
    pixels_per_group: int
    bytes_per_group: int
    width_alignment: int
    uses_container: bool

    @property
    def is_packed(self) -> bool:
        return not self.uses_container


STORAGE_FORMAT_SPECS: dict[StorageFormat, StorageFormatSpec] = {
    "unpacked": StorageFormatSpec(
        key="unpacked",
        label="Unpacked",
        fixed_bit_depth=None,
        pixels_per_group=1,
        bytes_per_group=0,
        width_alignment=1,
        uses_container=True,
    ),
    "mipi_raw10": StorageFormatSpec(
        key="mipi_raw10",
        label="MIPI RAW10",
        fixed_bit_depth=10,
        pixels_per_group=4,
        bytes_per_group=5,
        width_alignment=4,
        uses_container=False,
    ),
    "mipi_raw12": StorageFormatSpec(
        key="mipi_raw12",
        label="MIPI RAW12",
        fixed_bit_depth=12,
        pixels_per_group=2,
        bytes_per_group=3,
        width_alignment=4,
        uses_container=False,
    ),
    "mipi_raw14": StorageFormatSpec(
        key="mipi_raw14",
        label="MIPI RAW14",
        fixed_bit_depth=14,
        pixels_per_group=4,
        bytes_per_group=7,
        width_alignment=4,
        uses_container=False,
    ),
}


def storage_format_spec(storage_format: StorageFormat) -> StorageFormatSpec:
    return STORAGE_FORMAT_SPECS[storage_format]


def container_bit_count(container_dtype: ContainerDType) -> int:
    return 8 if container_dtype == "uint8" else 16


def container_byte_count(container_dtype: ContainerDType) -> int:
    return container_bit_count(container_dtype) // 8


def minimum_row_bytes(
    width: int,
    storage_format: StorageFormat,
    container_dtype: ContainerDType | None,
) -> int:
    """Return bytes occupied by valid pixels in one row, excluding padding."""

    spec = storage_format_spec(storage_format)
    if spec.uses_container:
        if container_dtype is None:
            raise ValueError("Unpacked RAW requires a sample container")
        return width * container_byte_count(container_dtype)
    if width % spec.width_alignment:
        raise ValueError(
            f"{spec.label} width must be a multiple of " f"{spec.width_alignment} pixels"
        )
    return width // spec.pixels_per_group * spec.bytes_per_group
