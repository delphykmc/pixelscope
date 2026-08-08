from __future__ import annotations

from collections import OrderedDict
from collections.abc import Collection


class ResidencyManager:
    """Track native decoded-source bytes and plan protected LRU eviction.

    The manager owns policy state only. It never imports Qt, looks up an
    ``ImageDocument``, or releases source arrays. Callers apply returned eviction
    candidates and then remove the corresponding accounting entries.
    """

    def __init__(self, budget_bytes: int) -> None:
        if not isinstance(budget_bytes, int) or isinstance(budget_bytes, bool):
            raise TypeError("source residency budget must be int")
        if budget_bytes <= 0:
            raise ValueError("source residency budget must be positive")
        self._budget_bytes = budget_bytes
        self._used_bytes = 0
        self._resident_bytes: OrderedDict[str, int] = OrderedDict()

    @property
    def budget_bytes(self) -> int:
        return self._budget_bytes

    @property
    def used_bytes(self) -> int:
        return self._used_bytes

    @property
    def resident_count(self) -> int:
        return len(self._resident_bytes)

    @property
    def over_budget_bytes(self) -> int:
        return max(0, self._used_bytes - self._budget_bytes)

    @property
    def resident_document_ids(self) -> tuple[str, ...]:
        """Return resident IDs from least to most recently used."""

        return tuple(self._resident_bytes)

    def record(self, document_id: str, source_nbytes: int) -> None:
        """Record an exact resident source size without implicitly touching it."""

        if not isinstance(document_id, str):
            raise TypeError("document_id must be str")
        if not document_id:
            raise ValueError("document_id must not be empty")
        if not isinstance(source_nbytes, int) or isinstance(source_nbytes, bool):
            raise TypeError("source_nbytes must be int")
        if source_nbytes <= 0:
            raise ValueError("source_nbytes must be positive")

        previous = self._resident_bytes.get(document_id)
        if previous is None:
            self._resident_bytes[document_id] = source_nbytes
            self._used_bytes += source_nbytes
            return
        self._resident_bytes[document_id] = source_nbytes
        self._used_bytes += source_nbytes - previous

    def touch(self, document_id: str) -> bool:
        """Promote a resident document to MRU, returning whether it existed."""

        if document_id not in self._resident_bytes:
            return False
        self._resident_bytes.move_to_end(document_id)
        return True

    def remove(self, document_id: str) -> bool:
        """Remove one resident accounting entry, returning whether it existed."""

        source_nbytes = self._resident_bytes.pop(document_id, None)
        if source_nbytes is None:
            return False
        self._used_bytes -= source_nbytes
        return True

    def eviction_candidates(self, protected_ids: Collection[str]) -> tuple[str, ...]:
        """Plan oldest unprotected removals needed to approach the soft budget.

        Protected bytes may keep the projected total above the budget. Planning
        does not mutate accounting so the caller can release document state first.
        """

        if self._used_bytes <= self._budget_bytes:
            return ()
        protected = set(protected_ids)
        projected_bytes = self._used_bytes
        candidates: list[str] = []
        for document_id, source_nbytes in self._resident_bytes.items():
            if projected_bytes <= self._budget_bytes:
                break
            if document_id in protected:
                continue
            candidates.append(document_id)
            projected_bytes -= source_nbytes
        return tuple(candidates)
