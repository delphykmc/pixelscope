from __future__ import annotations

import weakref
from collections.abc import Callable
from types import MethodType
from typing import Any


class OwnerCallback:
    """Callable view of an owner method that does not retain the owner."""

    def __init__(self, callback: Callable[..., Any]) -> None:
        self._function: Callable[..., Any]
        self._owner: weakref.ReferenceType[Any] | None
        if isinstance(callback, OwnerCallback):
            self._function = callback._function
            self._owner = callback._owner
            return
        owner = getattr(callback, "__self__", None)
        function = getattr(callback, "__func__", None)
        if owner is None or function is None:
            self._function = callback
            self._owner = None
        else:
            self._function = function
            self._owner = weakref.ref(owner)

    def resolve(self) -> Callable[..., Any]:
        if self._owner is None:
            return self._function
        owner = self._owner()
        if owner is None:
            raise RuntimeError("lifecycle owner was destroyed")
        return MethodType(self._function, owner)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.resolve()(*args, **kwargs)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, OwnerCallback):
            return NotImplemented
        owner = self._owner() if self._owner is not None else None
        other_owner = other._owner() if other._owner is not None else None
        return self._function == other._function and owner is other_owner
