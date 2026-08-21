"""Remote evaluation contracts, clients, and published IQA result domain."""

from pixelscope.remote.iqa_domain import LoadStatus, Result
from pixelscope.remote.iqa_reader import load_compact_scene
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_domain import RelativeStatisticV2, ResultV2
from pixelscope.remote.iqa_v2_math import compare_v2_sources
from pixelscope.remote.iqa_v2_reader import load_grid_scene

__all__ = [
    "LoadStatus",
    "RelativeStatisticV2",
    "Result",
    "ResultV2",
    "compare_v2_sources",
    "load_compact_scene",
    "load_grid_scene",
    "load_result",
]