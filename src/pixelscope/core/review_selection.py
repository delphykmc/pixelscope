from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field


def difference_sources_survive_selection(
    source_ids: Sequence[str] | None,
    selected_ids: Sequence[str],
) -> bool:
    """Return whether an existing Difference provenance survives Selected replacement."""

    if source_ids is None:
        return True
    selected = set(selected_ids)
    return all(source_id in selected for source_id in source_ids)


@dataclass
class ReviewSelectionState:
    """Temporary ID-only state captured by the first direct curation Pick."""

    baseline_selected_ids: tuple[str, ...] = ()
    picked_ids: set[str] = field(default_factory=set)
    active: bool = False

    def enter(self, selected_ids: Sequence[str]) -> None:
        """Capture a fresh curation baseline from ordered Selected IDs."""

        self.baseline_selected_ids = tuple(dict.fromkeys(str(value) for value in selected_ids))
        self.picked_ids.clear()
        self.active = True

    def exit(self) -> None:
        """Discard all temporary curation state without changing Selected."""

        self.active = False
        self.baseline_selected_ids = ()
        self.picked_ids.clear()

    def set_picked(self, document_id: str, picked: bool) -> bool:
        """Set one baseline source ID's picked membership; return whether state changed."""

        if not self.active or document_id not in self.baseline_selected_ids:
            return False
        before = document_id in self.picked_ids
        if picked:
            self.picked_ids.add(document_id)
        else:
            self.picked_ids.discard(document_id)
        return before != picked

    def clear_picks(self) -> bool:
        """Clear temporary membership while retaining the captured baseline."""

        if not self.active or not self.picked_ids:
            return False
        self.picked_ids.clear()
        return True

    @property
    def picked_count(self) -> int:
        return len(self.picked_ids)

    def kept_selected_ids(self) -> tuple[str, ...]:
        """Return picked IDs in original baseline Selected order, never pick order."""

        if not self.active:
            return ()
        return tuple(
            document_id
            for document_id in self.baseline_selected_ids
            if document_id in self.picked_ids
        )

    def matches_selected_ids(self, selected_ids: Sequence[str]) -> bool:
        """Return whether current Selected still matches the captured baseline exactly."""

        return self.active and tuple(selected_ids) == self.baseline_selected_ids
