from __future__ import annotations

from dataclasses import replace

import pytest

from pixelscope.core.preload import PreloadController, PreloadMemberRequest


def _request(generation: int, document_id: str) -> PreloadMemberRequest:
    return PreloadMemberRequest(
        plan_generation=generation,
        document_id=document_id,
        document_generation=0,
        source_path_identity=f"path:{document_id}",
        profile_identity="",
        require_exact_raw_size=False,
        normal_load_token=0,
    )


def test_no_plan_and_disabled_controller_own_no_targets() -> None:
    controller = PreloadController(enabled=False)

    assert controller.set_plan(("a",)) is None
    assert controller.current_plan is None
    assert controller.pending_document_ids == ()
    assert controller.diagnostics.enabled is False


@pytest.mark.parametrize("count", range(1, 7))
def test_create_plan_owns_one_bounded_group(count: int) -> None:
    controller = PreloadController()
    targets = tuple(f"document-{index}" for index in range(count))

    plan = controller.set_plan(targets)

    assert plan is not None
    assert plan.document_ids == targets
    assert controller.pending_document_ids == targets
    assert controller.diagnostics.planned_target_count == count


def test_same_plan_preserves_generation_and_member_progress() -> None:
    controller = PreloadController()
    first = controller.set_plan(("a", "b"))
    assert first is not None
    assert controller.complete_available_member(first.generation, "a")

    same = controller.set_plan(("a", "b"))

    assert same is first
    assert controller.pending_document_ids == ("b",)


def test_replacing_and_invalidating_plan_advance_identity() -> None:
    controller = PreloadController()
    first = controller.set_plan(("a",))
    assert first is not None
    second = controller.set_plan(("b",))
    assert second is not None

    assert second.generation == first.generation + 1
    assert not controller.complete_available_member(first.generation, "a")
    controller.invalidate()
    assert controller.current_plan is None
    assert controller.generation == second.generation + 1


def test_member_completion_and_full_completion_are_deterministic() -> None:
    controller = PreloadController()
    plan = controller.set_plan(("a", "b"))
    assert plan is not None
    request = _request(plan.generation, "a")
    assert controller.start_member(request)
    assert controller.request_is_current(request)
    assert not controller.request_is_current(replace(request, normal_load_token=1))
    assert not controller.start_member(request)
    assert controller.accept_success(plan.generation, "a", retained=True)
    controller.finish_worker(request)
    assert controller.pending_document_ids == ("b",)
    assert controller.complete_available_member(plan.generation, "b")
    assert controller.pending_document_ids == ()
    assert controller.diagnostics.successful_retained_count == 1
    assert controller.diagnostics.active_worker_count == 0


def test_running_request_promotion_is_once_only_and_leaves_speculative_counts() -> None:
    controller = PreloadController()
    plan = controller.set_plan(("a",))
    assert plan is not None
    request = _request(plan.generation, "a")
    assert controller.start_member(request)

    assert not controller.promote(request)
    assert controller.mark_running(request)
    assert controller.request_is_running(request)
    assert controller.promote(request)
    assert not controller.promote(request)
    assert controller.request_is_promoted(request)
    assert not controller.request_is_current(request)
    assert controller.diagnostics.promotion_count == 1
    assert controller.diagnostics.active_worker_count == 0


def test_stale_and_already_cancelled_requests_cannot_be_promoted() -> None:
    controller = PreloadController()
    plan = controller.set_plan(("a",))
    assert plan is not None
    request = _request(plan.generation, "a")
    assert controller.start_member(request)
    assert controller.mark_running(request)
    stale = replace(request, document_generation=1)

    assert not controller.promote(stale)
    controller.record_cancellation_request(request)
    assert not controller.request_is_running(request)
    assert not controller.promote(request)
    assert controller.diagnostics.cancellation_request_count == 1
    assert controller.diagnostics.promotion_count == 0


def test_promoted_request_survives_plan_invalidation_as_foreground_authority() -> None:
    controller = PreloadController()
    plan = controller.set_plan(("a",))
    assert plan is not None
    request = _request(plan.generation, "a")
    assert controller.start_member(request)
    assert controller.mark_running(request)
    assert controller.promote(request)

    controller.invalidate()
    controller.record_cancellation_request(request)

    assert controller.current_plan is None
    assert controller.request_is_promoted(request)
    assert controller.diagnostics.cancellation_request_count == 0
    assert controller.diagnostics.active_worker_count == 0
    controller.finish_worker(request)
    assert not controller.request_is_promoted(request)


def test_stale_generation_and_removed_target_are_rejected_and_counted() -> None:
    controller = PreloadController()
    first = controller.set_plan(("a",))
    assert first is not None
    second = controller.set_plan(("b",))
    assert second is not None

    assert not controller.accept_success(first.generation, "a", retained=True)
    assert not controller.accept_success(second.generation, "removed", retained=True)
    assert controller.diagnostics.stale_drop_count == 2
    assert controller.diagnostics.successful_retained_count == 0


def test_diagnostics_count_cancellation_and_failure_without_history() -> None:
    controller = PreloadController()
    plan = controller.set_plan(("a", "b"))
    assert plan is not None
    request = _request(plan.generation, "a")
    assert controller.start_member(request)
    controller.record_cancellation_request(request)
    assert controller.record_failure(plan.generation, "b")

    diagnostics = controller.diagnostics
    assert diagnostics.cancellation_request_count == 1
    assert diagnostics.failure_count == 1
    assert diagnostics.active_worker_count == 1
    assert diagnostics.promotion_count == 0


def test_cancellation_deduplication_is_bounded_to_active_worker_lifetime() -> None:
    controller = PreloadController()

    for index in range(100):
        document_id = f"document-{index}"
        plan = controller.set_plan((document_id,))
        assert plan is not None
        request = _request(plan.generation, document_id)
        assert controller.start_member(request)

        controller.record_cancellation_request(request)
        controller.record_cancellation_request(request)
        controller.invalidate()
        controller.record_cancellation_request(request)
        controller.finish_worker(request)

        assert controller.diagnostics.active_worker_count == 0
        assert controller._cancelled_requests == set()

    assert controller.diagnostics.cancellation_request_count == 100


@pytest.mark.parametrize("targets", ((), ("",), ("a", "a"), tuple(str(i) for i in range(7))))
def test_invalid_or_empty_target_groups_do_not_expand_ownership(
    targets: tuple[str, ...],
) -> None:
    controller = PreloadController()
    if not targets:
        assert controller.set_plan(targets) is None
    else:
        with pytest.raises(ValueError):
            controller.set_plan(targets)
