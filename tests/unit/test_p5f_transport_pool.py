from __future__ import annotations

from collections.abc import Callable

from pixelscope.remote.iqa_client import IqaJobClient
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
    JobState,
)
from pixelscope.remote.iqa_transport_pool import ReusableIqaClientPool


class _FakeClient(IqaJobClient):
    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.status_calls = 0
        self.close_calls = 0

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        raise AssertionError("not used")

    def get_status(self, job_id: str) -> IqaJobStatus:
        self.status_calls += 1
        return IqaJobStatus(job_id, JobState.QUEUED)

    def get_result(self, job_id: str) -> IqaResultReference:
        raise AssertionError("not used")

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        raise AssertionError("not used")

    def close(self) -> None:
        self.close_calls += 1


def _builder(store: list[_FakeClient]) -> Callable[[str], IqaJobClient]:
    def build(endpoint: str) -> IqaJobClient:
        client = _FakeClient(endpoint)
        store.append(client)
        return client

    return build


def test_reuses_idle_client_without_concurrent_sharing() -> None:
    clients: list[_FakeClient] = []
    pool = ReusableIqaClientPool(_builder(clients), max_idle_clients=2)

    first = pool.client("http://server/")
    assert first.get_status("job-1").state is JobState.QUEUED
    first.close()
    second = pool.client("http://server")
    assert second.get_status("job-1").state is JobState.QUEUED
    second.close()

    assert len(clients) == 1
    assert clients[0].status_calls == 2
    assert clients[0].close_calls == 0
    assert pool.diagnostics.clients_created == 1
    assert pool.diagnostics.leases_reused == 1
    assert pool.diagnostics.idle_clients == 1
    pool.close()
    assert clients[0].close_calls == 1


def test_concurrent_same_endpoint_leases_get_distinct_clients_and_bounded_idle() -> None:
    clients: list[_FakeClient] = []
    pool = ReusableIqaClientPool(_builder(clients), max_idle_clients=2)

    first = pool.client("http://server")
    second = pool.client("http://server")
    assert len(clients) == 2
    assert pool.diagnostics.active_leases == 2
    assert pool.diagnostics.max_active_leases == 2

    first.close()
    second.close()

    assert pool.diagnostics.idle_clients == 1
    assert pool.diagnostics.discarded_clients == 1
    assert sum(client.close_calls for client in clients) == 1
    pool.close()
    assert sum(client.close_calls for client in clients) == 2


def test_close_does_not_close_active_lease_under_worker() -> None:
    clients: list[_FakeClient] = []
    pool = ReusableIqaClientPool(_builder(clients))
    lease = pool.client("http://server")

    pool.close()

    assert pool.diagnostics.closed
    assert pool.diagnostics.active_leases == 1
    assert clients[0].close_calls == 0
    lease.close()
    assert pool.diagnostics.active_leases == 0
    assert clients[0].close_calls == 1
