# ruff: noqa: E721  # Exact JSON primitive types reject bool-as-int coercions.
"""Portable allowlisted interpretation of native source samples (W02).

These fields describe numerical decoding/spatial sampling, never names, paths,
sidecars, arbitrary raw-profile data, or original source byte arrays. Coordinates
and step/phase are (x, y); image/plane shapes are (rows, columns).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisNativeInterpretationV1:
    sampling_semantics: str = "direct"
    sample_step_xy: tuple[int, int] = (1, 1)
    sample_phase_xy: tuple[int, int] = (0, 0)
    sample_channel: str | None = None
    cfa_pattern: str | None = None
    cfa_phase_xy: tuple[int, int] | None = None
    raw_storage_format: str | None = None
    raw_container_dtype: str | None = None
    raw_row_stride_bytes: int | None = None
    raw_byte_offset: int | None = None
    raw_endianness: str | None = None
    raw_bit_alignment: str | None = None
    raw_packed_bit_order: str | None = None
    raw_black_levels: tuple[int, ...] | None = None
    raw_white_level: int | None = None
    yuv_layout: str | None = None
    yuv_chroma_step_xy: tuple[int, int] | None = None
    yuv_plane_shapes: tuple[tuple[int, int], ...] | None = None

    def __post_init__(self) -> None:
        if self.sampling_semantics not in ("direct", "cell_footprint", "point_lattice"):
            raise ValueError("invalid sample semantics")
        for pair, positive in (
            (self.sample_step_xy, True),
            (self.sample_phase_xy, False),
        ):
            if len(pair) != 2 or any(
                type(v) is not int or v < (1 if positive else 0) for v in pair
            ):
                raise ValueError("invalid sampling step/phase")
        if any(
            phase >= step
            for phase, step in zip(self.sample_phase_xy, self.sample_step_xy, strict=True)
        ):
            raise ValueError("phase is outside step")
        if self.sampling_semantics == "direct" and (
            self.sample_step_xy != (1, 1) or self.sample_phase_xy != (0, 0)
        ):
            raise ValueError("direct sampling requires unit step/zero phase")
        if self.sampling_semantics == "cell_footprint" and self.sample_phase_xy != (0, 0):
            raise ValueError("cell footprint must have zero phase")
        if self.sample_channel is not None and self.sample_channel not in (
            "R",
        ):
            raise ValueError("unknown sample channel")
        if self.cfa_pattern not in (None, "RGGB", "GRBG", "GBRG", "BGGR"):
            raise ValueError("unsupported Bayer CFA")
        if self.cfa_pattern is None:
            if self.cfa_phase_xy is not None:
                raise ValueError("CFA phase without Bayer pattern")
        elif (
            self.cfa_phase_xy is None
            or len(self.cfa_phase_xy) != 2
            or any(type(v) is not int or v not in (0, 1) for v in self.cfa_phase_xy)
        ):
            raise ValueError("Bayer phase requires two CFA parity offsets")
        if self.raw_storage_format not in (
            None,
            "unpacked",
            "packed_stream",
            "mipi_raw10",
            "mipi_raw12",
            "mipi_raw14",
        ):
            raise ValueError("unsupported RAW storage")
        if self.raw_container_dtype not in (None, "uint8", "uint16"):
            raise ValueError("unsupported RAW container")
        if self.raw_endianness not in (None, "little", "big"):
            raise ValueError("unsupported RAW endian")
        if self.raw_bit_alignment not in (None, "lsb", "msb"):
            raise ValueError("unsupported RAW bit alignment")
        if self.raw_packed_bit_order not in (None, "lsb", "msb"):
            raise ValueError("unsupported RAW bit order")
        for value, positive in (
            (self.raw_row_stride_bytes, True),
            (self.raw_byte_offset, False),
            (self.raw_white_level, True),
        ):
            if value is not None and (
                type(value) is not int or value < (1 if positive else 0) or value > 2**63 - 1
            ):
                raise ValueError("invalid RAW numeric metadata")
        if self.raw_black_levels is not None and (
            len(self.raw_black_levels) not in (1, 4)
            or any(type(v) is not int or v < 0 for v in self.raw_black_levels)
        ):
            raise ValueError("invalid RAW black levels")
        if self.yuv_layout not in (None, "YUV444", "YUV422", "YUV420"):
            raise ValueError("unsupported YUV layout")
        if self.yuv_layout is None:
            if self.yuv_chroma_step_xy is not None or self.yuv_plane_shapes is not None:
                raise ValueError("YUV geometry without YUV layout")
        else:
            expected = {
                "YUV444": (1, 1),
                "YUV422": (2, 1),
                "YUV420": (2, 2),
            }[self.yuv_layout]
            if self.yuv_chroma_step_xy != expected:
                raise ValueError("YUV layout/chroma step mismatch")
            shapes = self.yuv_plane_shapes
            if (
                shapes is None
                or len(shapes) != 3
                or any(
                    len(pair) != 2 or any(type(v) is not int or v <= 0 for v in pair)
                    for pair in shapes
                )
            ):
                raise ValueError("YUV requires three native plane shapes")
            y, u, v = shapes
            if u != v or y[0] != u[0] * expected[1] or y[1] != u[1] * expected[0]:
                raise ValueError("YUV plane geometry mismatch")

    def to_portable(self) -> dict[str, Any]:
        """One positive allowlist, shared by writer and strict parser."""
        return {
            "sampling_semantics": self.sampling_semantics,
            "sample_step_xy": list(self.sample_step_xy),
            "sample_phase_xy": list(self.sample_phase_xy),
            "sample_channel": self.sample_channel,
            "cfa_pattern": self.cfa_pattern,
            "cfa_phase_xy": list(self.cfa_phase_xy) if self.cfa_phase_xy is not None else None,
            "raw_storage_format": self.raw_storage_format,
            "raw_container_dtype": self.raw_container_dtype,
            "raw_row_stride_bytes": self.raw_row_stride_bytes,
            "raw_byte_offset": self.raw_byte_offset,
            "raw_endianness": self.raw_endianness,
            "raw_bit_alignment": self.raw_bit_alignment,
            "raw_packed_bit_order": self.raw_packed_bit_order,
            "raw_black_levels": (
                list(self.raw_black_levels) if self.raw_black_levels is not None else None
            ),
            "raw_white_level": self.raw_white_level,
            "yuv_layout": self.yuv_layout,
            "yuv_chroma_step_xy": (
                list(self.yuv_chroma_step_xy) if self.yuv_chroma_step_xy is not None else None
            ),
            "yuv_plane_shapes": (
                [list(pair) for pair in self.yuv_plane_shapes]
                if self.yuv_plane_shapes is not None
                else None
            ),
        }

    @classmethod
    def from_portable(cls, payload: object) -> AnalysisNativeInterpretationV1:
        if type(payload) is not dict or set(payload) != set(cls().to_portable()):
            raise ValueError("unknown native interpretation fields")
        obj: dict[str, Any] = payload

        def pair(key: str, nullable: bool = False) -> tuple[int, int] | None:
            value = obj[key]
            if nullable and value is None:
                return None
            if type(value) is not list or len(value) != 2 or any(type(v) is not int for v in value):
                raise ValueError("invalid native sampling pair")
            return value[0], value[1]

        shapes = obj["yuv_plane_shapes"]
        if shapes is not None and (type(shapes) is not list or len(shapes) != 3):
            raise ValueError("invalid YUV plane list")
        sample_step = pair("sample_step_xy")
        sample_phase = pair("sample_phase_xy")
        assert sample_step is not None and sample_phase is not None
        return cls(
            sampling_semantics=obj["sampling_semantics"],
            sample_step_xy=sample_step,
            sample_phase_xy=sample_phase,
            sample_channel=obj["sample_channel"],
            cfa_pattern=obj["cfa_pattern"],
            cfa_phase_xy=pair("cfa_phase_xy", nullable=True),
            raw_storage_format=obj["raw_storage_format"],
            raw_container_dtype=obj["raw_container_dtype"],
            raw_row_stride_bytes=obj["raw_row_stride_bytes"],
            raw_byte_offset=obj["raw_byte_offset"],
            raw_endianness=obj["raw_endianness"],
            raw_bit_alignment=obj["raw_bit_alignment"],
            raw_packed_bit_order=obj["raw_packed_bit_order"],
            raw_black_levels=(
                tuple(obj["raw_black_levels"])
                if type(obj["raw_black_levels"]) is list
                else obj["raw_black_levels"]
            ),
            raw_white_level=obj["raw_white_level"],
            yuv_layout=obj["yuv_layout"],
            yuv_chroma_step_xy=pair("yuv_chroma_step_xy", nullable=True),
            yuv_plane_shapes=(
                tuple(pair_value for pair_value in (cls._wire_plane(item) for item in shapes))
                if shapes is not None
                else None
            ),
        )

    @staticmethod
    def _wire_plane(value: object) -> tuple[int, int]:
        if type(value) is not list or len(value) != 2 or any(type(n) is not int for n in value):
            raise ValueError("invalid YUV plane shape")
        return value[0], value[1]
