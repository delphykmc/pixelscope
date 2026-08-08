from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FolderNavigationPlan:
    """One atomic move across registered document sequences."""

    document_ids: tuple[str, ...]
    folder_keys: tuple[str, ...]
    indices: tuple[int, ...]


def plan_folder_navigation(
    selection: Sequence[tuple[str, str]],
    folder_documents: Mapping[str, Sequence[str]],
    step: int,
) -> FolderNavigationPlan | None:
    """Plan one registered folder-position move without mutating runtime state."""

    if step not in (-1, 1):
        raise ValueError("folder navigation step must be -1 or 1")
    if not 1 <= len(selection) <= 6:
        return None

    folder_keys = tuple(folder_key for folder_key, _document_id in selection)
    if len(set(folder_keys)) != len(folder_keys):
        return None

    target_ids: list[str] = []
    target_indices: list[int] = []
    for folder_key, current_id in selection:
        registered_ids = folder_documents.get(folder_key)
        if registered_ids is None:
            return None
        try:
            current_index = registered_ids.index(current_id)
        except ValueError:
            return None
        target_index = current_index + step
        if target_index < 0 or target_index >= len(registered_ids):
            return None
        target_ids.append(registered_ids[target_index])
        target_indices.append(target_index)

    return FolderNavigationPlan(
        document_ids=tuple(target_ids),
        folder_keys=folder_keys,
        indices=tuple(target_indices),
    )
