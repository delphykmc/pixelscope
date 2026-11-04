"""Qt-free, runtime-only W05 comparison preset and A/B role contract.

These values describe *presentation*, not Files selection, Current Comparison Page,
source registration, residency, or a persistent Review source binding. No path,
alias, widget, Difference map, or synthetic durable source UUID is stored.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ComparisonPreset(str, Enum):
    WORKSPACE = "Workspace"
    ORIGINAL_2 = "Original 2"
    ORIGINAL_4 = "Original 4"
    AB_DIFF = "A/B/Diff"
    DIFF_FOCUS = "Diff Focus"


DifferenceState = Literal[
    "not-calculated", "cached-valid", "pending", "stale", "invalid"
]


@dataclass(frozen=True)
class ComparisonPair:
    """Ordered runtime ImageDocument identities; A and B are independent of Primary."""

    reference_id: str
    target_id: str

    def valid_on(self, page_ids: Sequence[str]) -> bool:
        return (
            bool(self.reference_id)
            and bool(self.target_id)
            and self.reference_id != self.target_id
            and self.reference_id in page_ids
            and self.target_id in page_ids
        )

    @property
    def source_ids(self) -> tuple[str, str]:
        return self.reference_id, self.target_id


@dataclass(frozen=True)
class ComparisonPlan:
    preset: ComparisonPreset
    source_ids: tuple[str, ...]
    pair: ComparisonPair | None
    available: bool
    difference_state: DifferenceState
    show_difference: bool
    explanation: str = ""


def plan_comparison(
    page_ids: Sequence[str],
    preset: ComparisonPreset,
    pair: ComparisonPair | None,
    *,
    cached_valid: bool = False,
    pending: bool = False,
    stale: bool = False,
) -> ComparisonPlan:
    """Choose a display subset without modifying page/source membership.

    A missing Difference map never authorizes either a computation or the display
    of a previously bound map. The caller must validate the live panel cache key,
    including generation and native channel, before passing `cached_valid=True`.
    """
    ids = tuple(page_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("comparison page contains duplicate source identities")
    if preset is ComparisonPreset.WORKSPACE:
        return ComparisonPlan(preset, ids, pair, True, "invalid", False)
    if pair is None or not pair.valid_on(ids):
        return ComparisonPlan(
            preset, (), pair, False, "invalid", False,
            "Reference A and Target B must be two sources on the current page.",
        )
    if preset is ComparisonPreset.ORIGINAL_2:
        return ComparisonPlan(preset, pair.source_ids, pair, True, "invalid", False)
    if preset is ComparisonPreset.ORIGINAL_4:
        if len(ids) < 4 or not set(pair.source_ids).issubset(ids[:4]):
            return ComparisonPlan(
                preset, (), pair, False, "invalid", False,
                "Original 4 requires four page sources and both pair roles within A/B/C/D.",
            )
        return ComparisonPlan(preset, ids[:4], pair, True, "invalid", False)
    if preset not in (ComparisonPreset.AB_DIFF, ComparisonPreset.DIFF_FOCUS):
        raise ValueError(f"unsupported comparison preset: {preset}")
    diff_state: DifferenceState = (
        "cached-valid" if cached_valid else "pending" if pending
        else "stale" if stale else "not-calculated"
    )
    source_ids = pair.source_ids if preset is ComparisonPreset.AB_DIFF else ()
    return ComparisonPlan(
        preset, source_ids, pair, True, diff_state, cached_valid,
        "" if cached_valid else f"Difference {diff_state}: use explicit Calculate in Analysis.",
    )
