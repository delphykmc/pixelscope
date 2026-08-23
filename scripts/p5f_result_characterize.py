from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from pixelscope.remote.iqa_domain import LoadStatus
from pixelscope.remote.iqa_explorer import IqaExplorerModel
from pixelscope.remote.iqa_result_reader import load_result
from pixelscope.remote.iqa_v2_domain import GridSceneDataV2, ResultV2
from pixelscope.remote.iqa_v2_reader import load_grid_scene

T = TypeVar("T")


def _timed(call: Callable[[], T]) -> tuple[T, float]:
    started = time.perf_counter()
    value = call()
    return value, max(0.0, (time.perf_counter() - started) * 1000.0)


def _grid_retained_nbytes(data: GridSceneDataV2) -> int:
    total = 0
    seen: set[int] = set()
    for compact in data.attributes.values():
        for value in (
            compact.weight_sum,
            compact.weighted_sum,
            compact.weighted_square_sum,
            compact.valid_count,
            compact.valid_mask,
        ):
            array = np.asarray(value)
            identity = id(value)
            if identity not in seen:
                seen.add(identity)
                total += int(array.nbytes)
    return total


def _full_npz_read(path: Path) -> tuple[int, int]:
    total_bytes = 0
    with np.load(path, allow_pickle=False) as archive:
        names = tuple(archive.files)
        for name in names:
            total_bytes += int(np.asarray(archive[name]).nbytes)
    return len(names), total_bytes


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Characterize an existing schema-v2 IQA Result without changing its files, "
            "caches, or numerical authority."
        )
    )
    parser.add_argument("result_root", type=Path)
    args = parser.parse_args()

    outcome, result_open_ms = _timed(lambda: load_result(args.result_root))
    if outcome.status is not LoadStatus.SUCCESS or not isinstance(outcome.result, ResultV2):
        reason = outcome.reason or "Result is not a readable schema-v2 result"
        print(json.dumps({"status": outcome.status.value, "reason": reason}, indent=2))
        return 2
    result = outcome.result
    if not result.scenes or not result.variants:
        print(
            json.dumps(
                {"status": "invalid", "reason": "Result has no Scenes/variants"},
                indent=2,
            )
        )
        return 2

    manifest_path = result.root / "manifest.json"
    manifest_payload, manifest_read_ms = _timed(manifest_path.read_bytes)
    summary_path = result.root / result.summary_artifact
    summary_info, summary_full_read_ms = _timed(lambda: _full_npz_read(summary_path))

    model = IqaExplorerModel(result)
    first_reference_id = result.variants[0].variant_id
    prepared, first_reference_ms = _timed(lambda: model.prepare_reference(first_reference_id))
    repeated, repeated_reference_ms = _timed(lambda: prepared.prepare_reference(first_reference_id))

    different_reference_id: str | None = None
    different_reference_ms: float | None = None
    if len(result.variants) > 1:
        different_reference_id = result.variants[1].variant_id
        _, different_reference_ms = _timed(
            lambda: prepared.prepare_reference(different_reference_id)
        )

    first_scene = result.scenes[0]
    grid_outcome, first_scene_grid_ms = _timed(
        lambda: load_grid_scene(result, first_scene.scene_id)
    )
    retained_grid_bytes: int | None = None
    if grid_outcome.succeeded and grid_outcome.data is not None:
        retained_grid_bytes = _grid_retained_nbytes(grid_outcome.data)

    report: dict[str, Any] = {
        "status": "success",
        "result_id": result.result_id,
        "schema_version": result.schema_version,
        "scene_count": len(result.scenes),
        "variant_count": len(result.variants),
        "attribute_count": len(result.attributes),
        "result_open_ms": result_open_ms,
        "manifest_read_ms": manifest_read_ms,
        "manifest_bytes": len(manifest_payload),
        "summary_full_read_ms": summary_full_read_ms,
        "summary_array_count": summary_info[0],
        "summary_uncompressed_array_bytes": summary_info[1],
        "first_reference_id": first_reference_id,
        "first_reference_prepare_ms": first_reference_ms,
        "repeated_reference_prepare_ms": repeated_reference_ms,
        "repeated_reference_reused_model": repeated is prepared,
        "different_reference_id": different_reference_id,
        "different_reference_prepare_ms": different_reference_ms,
        "first_scene_id": first_scene.scene_id,
        "first_scene_grid_load_ms": first_scene_grid_ms,
        "first_scene_declared_grid_uncompressed_bytes": first_scene.grid_uncompressed_size,
        "first_scene_retained_grid_array_bytes": retained_grid_bytes,
        "grid_status": grid_outcome.status.value,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if grid_outcome.succeeded else 2


if __name__ == "__main__":
    raise SystemExit(main())
