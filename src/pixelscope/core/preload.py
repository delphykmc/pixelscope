from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PreloadPlan:
    """Identity and bounded target ownership for one speculative position."""

    generation: int
    document_ids: tuple[str, ...]


@dataclass(frozen=True)
class PreloadMemberRequest:
    """Immutable source authority captured before one speculative decode."""

    plan_generation: int
    document_id: str
    document_generation: int
    source_path_identity: str
    profile_identity: str
    require_exact_raw_size: bool
    normal_load_token: int


@dataclass(frozen=True)
class PreloadDiagnostics:
    enabled: bool
    planned_target_count: int
    active_worker_count: int
    successful_retained_count: int
    stale_drop_count: int
    cancellation_request_count: int
    failure_count: int
    promotion_count: int


class PreloadController:
    """Qt-free state authority for exactly one next-position preload plan."""

    def __init__(self, enabled: bool = True) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("preload enabled must be bool")
        self._enabled = enabled
        self._generation = 0
        self._plan: PreloadPlan | None = None
        self._completed_ids: set[str] = set()
        self._active_requests: dict[tuple[int, str], PreloadMemberRequest] = {}
        self._running_requests: set[tuple[int, str]] = set()
        self._promoted_requests: set[tuple[int, str]] = set()
        self._cancelled_requests: set[tuple[int, str]] = set()
        self._successful_retained_count = 0
        self._stale_drop_count = 0
        self._cancellation_request_count = 0
        self._failure_count = 0
        self._promotion_count = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def generation(self) -> int:
        return self._generation

    @property
    def current_plan(self) -> PreloadPlan | None:
        return self._plan

    @property
    def pending_document_ids(self) -> tuple[str, ...]:
        if self._plan is None:
            return ()
        return tuple(
            document_id
            for document_id in self._plan.document_ids
            if document_id not in self._completed_ids
            and (self._plan.generation, document_id) not in self._active_requests
        )

    @property
    def diagnostics(self) -> PreloadDiagnostics:
        speculative_active_count = sum(
            request_key not in self._promoted_requests for request_key in self._active_requests
        )
        return PreloadDiagnostics(
            enabled=self._enabled,
            planned_target_count=len(self._plan.document_ids) if self._plan is not None else 0,
            active_worker_count=speculative_active_count,
            successful_retained_count=self._successful_retained_count,
            stale_drop_count=self._stale_drop_count,
            cancellation_request_count=self._cancellation_request_count,
            failure_count=self._failure_count,
            promotion_count=self._promotion_count,
        )

    def set_plan(self, document_ids: Sequence[str]) -> PreloadPlan | None:
        """Own a new target group, or preserve progress for an identical group."""

        targets = tuple(document_ids)
        if not self._enabled or not targets:
            self.invalidate()
            return None
        if not 1 <= len(targets) <= 6:
            raise ValueError("preload plan must contain one to six targets")
        if any(not isinstance(document_id, str) or not document_id for document_id in targets):
            raise ValueError("preload target IDs must be non-empty strings")
        if len(set(targets)) != len(targets):
            raise ValueError("preload target IDs must be unique")
        if self._plan is not None and self._plan.document_ids == targets:
            return self._plan

        self._generation += 1
        self._plan = PreloadPlan(self._generation, targets)
        self._completed_ids.clear()
        return self._plan

    def invalidate(self) -> None:
        if self._plan is None:
            return
        self._generation += 1
        self._plan = None
        self._completed_ids.clear()

    def start_member(self, request: PreloadMemberRequest) -> bool:
        if not self._is_current_target(request.plan_generation, request.document_id):
            return False
        if request.document_id in self._completed_ids:
            return False
        request_key = self._request_key(request)
        if request_key in self._active_requests:
            return False
        self._active_requests[request_key] = request
        return True

    def mark_running(self, request: PreloadMemberRequest) -> bool:
        """Record that an accepted request has physically begun execution."""

        request_key = self._request_key(request)
        if self._active_requests.get(request_key) != request:
            return False
        if request_key in self._cancelled_requests:
            return False
        self._running_requests.add(request_key)
        return True

    def request_is_current(self, request: PreloadMemberRequest) -> bool:
        request_key = self._request_key(request)
        return (
            self._is_current_target(request.plan_generation, request.document_id)
            and self._active_requests.get(request_key) == request
            and request_key not in self._promoted_requests
        )

    def request_is_running(self, request: PreloadMemberRequest) -> bool:
        request_key = self._request_key(request)
        return (
            self._active_requests.get(request_key) == request
            and request_key in self._running_requests
            and request_key not in self._cancelled_requests
        )

    def request_is_promoted(self, request: PreloadMemberRequest) -> bool:
        request_key = self._request_key(request)
        return (
            self._active_requests.get(request_key) == request
            and request_key in self._promoted_requests
        )

    def promote(self, request: PreloadMemberRequest) -> bool:
        """Transfer one exact running speculative request to foreground authority."""

        request_key = self._request_key(request)
        if not self.request_is_current(request):
            return False
        if request_key not in self._running_requests:
            return False
        if request_key in self._cancelled_requests or request_key in self._promoted_requests:
            return False
        self._promoted_requests.add(request_key)
        self._promotion_count += 1
        return True

    def complete_available_member(self, generation: int, document_id: str) -> bool:
        if not self._is_current_target(generation, document_id):
            return False
        self._completed_ids.add(document_id)
        return True

    def accept_success(self, generation: int, document_id: str, *, retained: bool) -> bool:
        if not self._is_current_target(generation, document_id):
            self._stale_drop_count += 1
            return False
        request_key = (generation, document_id)
        if request_key in self._promoted_requests:
            return False
        self._completed_ids.add(document_id)
        if retained:
            self._successful_retained_count += 1
        return True

    def record_failure(self, generation: int, document_id: str) -> bool:
        if not self._is_current_target(generation, document_id):
            return False
        request_key = (generation, document_id)
        if request_key in self._promoted_requests:
            return False
        self._failure_count += 1
        self._completed_ids.add(document_id)
        return True

    def record_stale_drop(self) -> None:
        self._stale_drop_count += 1

    def record_cancellation_request(self, request: PreloadMemberRequest) -> None:
        request_key = self._request_key(request)
        if request_key in self._promoted_requests:
            return
        if (
            self._active_requests.get(request_key) == request
            and request_key not in self._cancelled_requests
        ):
            self._cancelled_requests.add(request_key)
            self._cancellation_request_count += 1

    def finish_worker(self, request: PreloadMemberRequest) -> None:
        request_key = self._request_key(request)
        if self._active_requests.get(request_key) == request:
            self._active_requests.pop(request_key)
            self._running_requests.discard(request_key)
            self._promoted_requests.discard(request_key)
            self._cancelled_requests.discard(request_key)

    @staticmethod
    def _request_key(request: PreloadMemberRequest) -> tuple[int, str]:
        return request.plan_generation, request.document_id

    def _is_current_target(self, generation: int, document_id: str) -> bool:
        return (
            self._plan is not None
            and self._plan.generation == generation
            and document_id in self._plan.document_ids
        )
