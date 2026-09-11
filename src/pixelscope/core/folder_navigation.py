from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class FolderNavigationPlan:
    """One atomic move across registered document sequences."""

    document_ids: tuple[str, ...]
    folder_keys: tuple[str, ...]
    indices: tuple[int, ...]


@dataclass(frozen=True)
class FolderComparisonBootstrapPlan:
    """One same-ordinal comparison target in registered folder order."""

    anchor_folder_key: str
    target_folder_key: str
    document_id: str
    ordinal_index: int


def _comparison_targets(
    selection: Sequence[tuple[str, str]],
    folder_documents: Mapping[str, Sequence[str]],
    folder_order: Sequence[str],
    anchor_document_id: str,
) -> tuple[tuple[FolderComparisonBootstrapPlan, ...], str, int] | None:
    """Validate a comparison context and return targets plus anchor metadata."""

    # Five selected folders leave a sixth slot for the comparison target.  A
    # full six-folder selection is valid UI state, but has no bootstrap target.
    if not 1 <= len(selection) <= 6:
        return None
    if len(selection) == 6:
        return (), "", -1
    selected_folders = tuple(folder_key for folder_key, _document_id in selection)
    if len(set(selected_folders)) != len(selected_folders):
        return None
    ordered_folders = tuple(folder_order)
    if len(set(ordered_folders)) != len(ordered_folders):
        return None
    if any(folder_key not in folder_documents for folder_key in ordered_folders):
        return None
    if any(folder_key not in ordered_folders for folder_key in selected_folders):
        return None

    anchor_folder_key: str | None = None
    ordinal_index = -1
    for folder_key, document_id in selection:
        documents = folder_documents[folder_key]
        if document_id not in documents:
            return None
        if document_id == anchor_document_id:
            if anchor_folder_key is not None:
                return None
            anchor_folder_key = folder_key
            ordinal_index = documents.index(document_id)
    if anchor_folder_key is None:
        return None

    targets = tuple(
        FolderComparisonBootstrapPlan(
            anchor_folder_key=anchor_folder_key,
            target_folder_key=folder_key,
            document_id=folder_documents[folder_key][ordinal_index],
            ordinal_index=ordinal_index,
        )
        for folder_key in ordered_folders
        if folder_key not in selected_folders and len(folder_documents[folder_key]) > ordinal_index
    )
    return targets, anchor_folder_key, ordinal_index


def plan_folder_comparison_targets(
    selection: Sequence[tuple[str, str]],
    folder_documents: Mapping[str, Sequence[str]],
    folder_order: Sequence[str],
    anchor_document_id: str,
) -> tuple[FolderComparisonBootstrapPlan, ...]:
    """Return same-ordinal targets in registered order, without mutation."""

    planned = _comparison_targets(selection, folder_documents, folder_order, anchor_document_id)
    return () if planned is None else planned[0]


def plan_folder_comparison_direction(
    selection: Sequence[tuple[str, str]],
    folder_documents: Mapping[str, Sequence[str]],
    folder_order: Sequence[str],
    anchor_document_id: str,
    step: int,
) -> FolderComparisonBootstrapPlan | None:
    """Return the nearest same-ordinal target before or after the anchor."""

    if step not in (-1, 1):
        raise ValueError("folder comparison direction must be -1 or 1")
    planned = _comparison_targets(selection, folder_documents, folder_order, anchor_document_id)
    if planned is None or planned[0] == ():
        return None
    targets, anchor_folder_key, _ordinal_index = planned
    target_keys = [target.target_folder_key for target in targets]
    anchor_position = tuple(folder_order).index(anchor_folder_key)
    candidate_positions = (
        range(anchor_position + step, len(folder_order), step)
        if step == 1
        else range(anchor_position - 1, -1, -1)
    )
    for position in candidate_positions:
        if folder_order[position] in target_keys:
            return targets[target_keys.index(folder_order[position])]
    return None


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
