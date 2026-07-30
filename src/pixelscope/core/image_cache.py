from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from typing import Generic, TypeVar

ValueT = TypeVar("ValueT")


class ImageCache(Generic[ValueT]):
    """Small bounded LRU cache used for derived image data."""

    def __init__(self, capacity: int = 16) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._values: OrderedDict[Hashable, ValueT] = OrderedDict()

    def get(self, key: Hashable) -> ValueT | None:
        value = self._values.get(key)
        if value is not None:
            self._values.move_to_end(key)
        return value

    def put(self, key: Hashable, value: ValueT) -> None:
        self._values[key] = value
        self._values.move_to_end(key)
        while len(self._values) > self._capacity:
            self._values.popitem(last=False)

    def clear(self) -> None:
        self._values.clear()
