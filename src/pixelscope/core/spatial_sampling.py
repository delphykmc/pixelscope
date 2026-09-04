"""Qt-free reference-space to native-sample spatial mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from pixelscope.core.roi import RoiBounds

SamplingSemantics = Literal["direct", "cell_footprint", "point_lattice"]


@dataclass(frozen=True)
class SpatialSampling:
    """Describe how a native sample grid relates to an interaction reference grid.

    Shapes use ``(rows, columns)``. Public coordinates use ``(x, y)`` so callers
    remain consistent with the rest of the image and ROI APIs.
    """

    reference_shape: tuple[int, int]
    sample_shape: tuple[int, int]
    sampling_semantics: SamplingSemantics = "direct"
    row_step: int = 1
    column_step: int = 1
    row_phase: int = 0
    column_phase: int = 0

    def __post_init__(self) -> None:
        reference_rows, reference_columns = self._validated_shape(
            self.reference_shape, "reference_shape"
        )
        sample_rows, sample_columns = self._validated_shape(self.sample_shape, "sample_shape")
        if self.sampling_semantics not in ("direct", "cell_footprint", "point_lattice"):
            raise ValueError(f"unsupported sampling semantics: {self.sampling_semantics}")
        for name, value in (
            ("row_step", self.row_step),
            ("column_step", self.column_step),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name, value in (
            ("row_phase", self.row_phase),
            ("column_phase", self.column_phase),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")

        if self.sampling_semantics == "direct":
            if (
                self.sample_shape != self.reference_shape
                or self.row_step != 1
                or self.column_step != 1
                or self.row_phase != 0
                or self.column_phase != 0
            ):
                raise ValueError(
                    "direct sampling requires matching shapes and unit zero-phase steps"
                )
            return

        if self.sampling_semantics == "cell_footprint":
            if self.row_phase != 0 or self.column_phase != 0:
                raise ValueError("cell_footprint sampling does not support a phase")
            expected_shape = (
                self._ceil_div(reference_rows, self.row_step),
                self._ceil_div(reference_columns, self.column_step),
            )
        else:
            if self.row_phase >= self.row_step or self.column_phase >= self.column_step:
                raise ValueError("point_lattice phase must be smaller than its step")
            expected_shape = (
                self._lattice_count(reference_rows, self.row_step, self.row_phase),
                self._lattice_count(reference_columns, self.column_step, self.column_phase),
            )
        if expected_shape != (sample_rows, sample_columns):
            raise ValueError(
                f"{self.sampling_semantics} sample_shape must be {expected_shape}, "
                f"got {self.sample_shape}"
            )

    @staticmethod
    def _validated_shape(shape: tuple[int, int], name: str) -> tuple[int, int]:
        if len(shape) != 2:
            raise ValueError(f"{name} must contain rows and columns")
        rows, columns = shape
        if (
            not isinstance(rows, int)
            or isinstance(rows, bool)
            or not isinstance(columns, int)
            or isinstance(columns, bool)
            or rows <= 0
            or columns <= 0
        ):
            raise ValueError(f"{name} dimensions must be positive integers")
        return rows, columns

    @staticmethod
    def _ceil_div(value: int, divisor: int) -> int:
        return -(-value // divisor)

    @staticmethod
    def _lattice_count(length: int, step: int, phase: int) -> int:
        if phase >= length:
            return 0
        return ((length - 1 - phase) // step) + 1

    @classmethod
    def identity(cls, shape: tuple[int, int]) -> SpatialSampling:
        """Return direct identity sampling for a full-resolution image."""

        return cls(reference_shape=shape, sample_shape=shape)

    @classmethod
    def cell_footprint(
        cls,
        reference_shape: tuple[int, int],
        sample_shape: tuple[int, int],
        *,
        row_step: int,
        column_step: int,
    ) -> SpatialSampling:
        """Return a chroma-style sample-cell mapping."""

        return cls(
            reference_shape=reference_shape,
            sample_shape=sample_shape,
            sampling_semantics="cell_footprint",
            row_step=row_step,
            column_step=column_step,
        )

    @classmethod
    def point_lattice(
        cls,
        reference_shape: tuple[int, int],
        sample_shape: tuple[int, int],
        *,
        row_step: int,
        column_step: int,
        row_phase: int,
        column_phase: int,
    ) -> SpatialSampling:
        """Return a CFA-style sparse point-lattice mapping."""

        return cls(
            reference_shape=reference_shape,
            sample_shape=sample_shape,
            sampling_semantics="point_lattice",
            row_step=row_step,
            column_step=column_step,
            row_phase=row_phase,
            column_phase=column_phase,
        )

    @property
    def semantics(self) -> SamplingSemantics:
        """Short alias used by presentation/inspection callers."""

        return self.sampling_semantics

    @property
    def presentation_rect(self) -> tuple[float, float, float, float]:
        """Return the native ImageItem rect in reference coordinates.

        Direct and footprint samples cover the whole reference image. Point
        lattice samples use a phase-aware macrocell centered on each actual CFA
        site; the viewer clips that rect to the reference view.
        """

        reference_rows, reference_columns = self.reference_shape
        if self.sampling_semantics != "point_lattice":
            return 0.0, 0.0, float(reference_columns), float(reference_rows)
        sample_rows, sample_columns = self.sample_shape
        return (
            float(self.column_phase) + 0.5 - float(self.column_step) / 2.0,
            float(self.row_phase) + 0.5 - float(self.row_step) / 2.0,
            float(sample_columns * self.column_step),
            float(sample_rows * self.row_step),
        )

    def reference_to_sample(self, x: int, y: int) -> tuple[int, int] | None:
        """Map one reference coordinate to a native sample, when one exists."""

        reference_rows, reference_columns = self.reference_shape
        if x < 0 or y < 0 or x >= reference_columns or y >= reference_rows:
            return None
        if self.sampling_semantics == "direct":
            return x, y
        if self.sampling_semantics == "cell_footprint":
            return x // self.column_step, y // self.row_step
        if (x - self.column_phase) % self.column_step != 0 or (
            y - self.row_phase
        ) % self.row_step != 0:
            return None
        sample_x = (x - self.column_phase) // self.column_step
        sample_y = (y - self.row_phase) // self.row_step
        sample_rows, sample_columns = self.sample_shape
        if sample_x < 0 or sample_y < 0 or sample_x >= sample_columns or sample_y >= sample_rows:
            return None
        return sample_x, sample_y

    def sample_coordinate_at_reference(self, x: int, y: int) -> tuple[int, int] | None:
        """Explicitly named alias for :meth:`reference_to_sample`."""

        return self.reference_to_sample(x, y)

    def sample_reference_site(self, sample_x: int, sample_y: int) -> tuple[int, int] | None:
        """Return the actual reference lattice site (or cell origin) of a sample."""

        sample_rows, sample_columns = self.sample_shape
        if sample_x < 0 or sample_y < 0 or sample_x >= sample_columns or sample_y >= sample_rows:
            return None
        return (
            self.column_phase + sample_x * self.column_step,
            self.row_phase + sample_y * self.row_step,
        )

    def reference_roi_to_sample_bounds(self, bounds: RoiBounds) -> RoiBounds | None:
        """Map one half-open reference ROI to its intersecting native samples."""

        from pixelscope.core.roi import RoiBounds

        reference_rows, reference_columns = self.reference_shape
        if bounds.right > reference_columns or bounds.bottom > reference_rows:
            raise ValueError("ROI extends beyond the reference image")
        if self.sampling_semantics == "direct":
            return bounds
        if self.sampling_semantics == "cell_footprint":
            start_x = bounds.x // self.column_step
            start_y = bounds.y // self.row_step
            end_x = self._ceil_div(bounds.right, self.column_step)
            end_y = self._ceil_div(bounds.bottom, self.row_step)
        else:
            start_x = self._ceil_div(bounds.x - self.column_phase, self.column_step)
            start_y = self._ceil_div(bounds.y - self.row_phase, self.row_step)
            end_x = self._ceil_div(bounds.right - self.column_phase, self.column_step)
            end_y = self._ceil_div(bounds.bottom - self.row_phase, self.row_step)

        sample_rows, sample_columns = self.sample_shape
        start_x = min(max(start_x, 0), sample_columns)
        start_y = min(max(start_y, 0), sample_rows)
        end_x = min(max(end_x, 0), sample_columns)
        end_y = min(max(end_y, 0), sample_rows)
        if end_x <= start_x or end_y <= start_y:
            return None
        return RoiBounds(start_x, start_y, end_x - start_x, end_y - start_y)

    def sample_bounds_for_reference_roi(self, bounds: RoiBounds) -> RoiBounds | None:
        """Explicit alias for :meth:`reference_roi_to_sample_bounds`."""

        return self.reference_roi_to_sample_bounds(bounds)
