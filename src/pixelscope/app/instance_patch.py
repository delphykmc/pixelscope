from __future__ import annotations

import weakref
from typing import Any

_MISSING = object()


class InstanceAttributePatch:
    """Own one persistent instance override and restore its exact prior state."""

    def __init__(
        self,
        target: object,
        attribute: str,
        replacement: object,
    ) -> None:
        try:
            target_dict = vars(target)
        except TypeError as exc:
            raise TypeError("runtime patch target must expose an instance __dict__") from exc
        try:
            self._target_ref = weakref.ref(target)
        except TypeError as exc:
            raise TypeError("runtime patch target must support weak references") from exc

        self.attribute = attribute
        self._previous: object = target_dict.get(attribute, _MISSING)
        self._replacement_id = id(replacement)
        self._active = True
        setattr(target, attribute, replacement)

    @property
    def active(self) -> bool:
        return self._active

    def restore(self) -> None:
        """Restore the exact instance slot that existed before this patch.

        A class-defined descriptor is restored by deleting the instance override,
        not by storing a bound method on the instance. Stacked patches must unwind
        in LIFO order; a different current value is treated as an ordering defect.
        """

        if not self._active:
            return
        target = self._target_ref()
        if target is None:
            self._release()
            return

        current = vars(target).get(self.attribute, _MISSING)
        if current is _MISSING or id(current) != self._replacement_id:
            raise RuntimeError(
                f"runtime patch restore order violation for {type(target).__name__}."
                f"{self.attribute}"
            )

        previous = self._previous
        if previous is _MISSING:
            delattr(target, self.attribute)
        else:
            setattr(target, self.attribute, previous)
        self._release()

    def _release(self) -> None:
        self._previous = _MISSING
        self._replacement_id = 0
        self._active = False


class InstancePatchSet:
    """Restore one feature owner's instance patches in reverse install order."""

    def __init__(self) -> None:
        self._patches: list[InstanceAttributePatch] = []

    @property
    def active_count(self) -> int:
        return sum(patch.active for patch in self._patches)

    def install(self, target: Any, attribute: str, replacement: object) -> object:
        patch = InstanceAttributePatch(target, attribute, replacement)
        self._patches.append(patch)
        return replacement

    def restore_all(self) -> None:
        for patch in reversed(self._patches):
            patch.restore()
        self._patches.clear()
