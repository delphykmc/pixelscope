from __future__ import annotations

import weakref
from collections.abc import Callable
from types import MethodType
from typing import Any


_MISSING = object()


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


class WeakOwnerHook:
    """Instance-installed callable whose owner edge remains non-owning."""

    def __init__(self, owner: Any, function: Callable[..., Any]) -> None:
        self._owner = weakref.ref(owner)
        self._function = function

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        owner = self._owner()
        if owner is None:
            raise RuntimeError("lifecycle hook owner was destroyed")
        return self._function(owner, *args, **kwargs)


class WeakOwnerAttribute:
    """Data descriptor that exposes a real object while storing only a weak reference."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._storage_name = f"__pixelscope_weak_owner_{name}"

    def __get__(self, instance: Any, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        stored = instance.__dict__.get(self._storage_name, _MISSING)
        if stored is _MISSING:
            raise AttributeError(self._name)
        if stored is None:
            return None
        value = stored()
        if value is None:
            raise RuntimeError(f"{self._name} lifecycle owner was destroyed")
        return value

    def __set__(self, instance: Any, value: Any) -> None:
        instance.__dict__.pop(self._name, None)
        instance.__dict__[self._storage_name] = None if value is None else weakref.ref(value)


class WeakOwnerTupleAttribute:
    """Tuple-valued variant of WeakOwnerAttribute for owned Qt dependency groups."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._storage_name = f"__pixelscope_weak_owner_tuple_{name}"

    def __get__(self, instance: Any, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        stored = instance.__dict__.get(self._storage_name, _MISSING)
        if stored is _MISSING:
            raise AttributeError(self._name)
        values: list[Any] = []
        for item in stored:
            if item is None:
                values.append(None)
                continue
            value = item()
            if value is None:
                raise RuntimeError(f"{self._name} lifecycle dependency was destroyed")
            values.append(value)
        return tuple(values)

    def __set__(self, instance: Any, value: tuple[Any, ...]) -> None:
        instance.__dict__.pop(self._name, None)
        instance.__dict__[self._storage_name] = tuple(
            None if item is None else weakref.ref(item) for item in value
        )


class OwnerCallbackAttribute:
    """Data descriptor that stores assigned callables through OwnerCallback."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._storage_name = f"__pixelscope_owner_callback_{name}"

    def __get__(self, instance: Any, owner: type[Any] | None = None) -> Any:
        if instance is None:
            return self
        stored = instance.__dict__.get(self._storage_name, _MISSING)
        if stored is _MISSING:
            raise AttributeError(self._name)
        return stored

    def __set__(self, instance: Any, value: Callable[..., Any]) -> None:
        instance.__dict__.pop(self._name, None)
        instance.__dict__[self._storage_name] = OwnerCallback(value)
