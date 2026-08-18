"""Remote evaluation contracts, clients, and published IQA result domain."""

from pixelscope.remote.iqa_domain import LoadStatus, Result
from pixelscope.remote.iqa_reader import load_compact_scene, load_result

__all__ = ["LoadStatus", "Result", "load_compact_scene", "load_result"]
