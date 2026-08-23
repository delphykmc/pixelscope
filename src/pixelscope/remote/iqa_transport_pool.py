"""Bounded reusable HTTP-client leases for the Remote IQA transport."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from pixelscope.remote.iqa_client import HttpIqaJobClient, IqaJobClient
from pixelscope.remote.iqa_submission import (
    IqaJobCreated,
    IqaJobRequest,
    IqaJobStatus,
    IqaResultReference,
)


@dataclass(frozen=True)
class IqaTransportPoolDiagnostics:
    """Small immutable transport-lifetime snapshot; no request bodies are retained."""

    clients_created: int
    leases_reused: int
    active_leases: int
    max_active_leases: int
    idle_clients: int
    discarded_clients: int
    closed: bool


class _ClientLease(IqaJobClient):
    def __init__(
        self,
        owner: ReusableIqaClientPool,
        endpoint: str,
        client: IqaJobClient,
    ) -> None:
        self._owner = owner
        self._endpoint = endpoint
        self._client = client
        self._closed = False

    def create_job(self, request: IqaJobRequest) -> IqaJobCreated:
        return self._client.create_job(request)

    def get_status(self, job_id: str) -> IqaJobStatus:
        return self._client.get_status(job_id)

    def get_result(self, job_id: str) -> IqaResultReference:
        return self._client.get_result(job_id)

    def cancel_job(self, job_id: str) -> IqaJobStatus:
        return self._client.cancel_job(job_id)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._owner._release(self._endpoint, self._client)


class ReusableIqaClientPool:
    """Lease one client per worker while retaining only a bounded idle set.

    The production P5-C helpers still call ``close()`` after every operation. A lease
    interprets that call as "return to the pool" so the underlying ``httpx.Client`` can
    keep its connection pool across create/status/result/cancel requests without ever
    sharing one active client between worker threads.
    """

    def __init__(
        self,
        client_builder: Callable[[str], IqaJobClient] | None = None,
        *,
        max_idle_clients: int = 2,
    ) -> None:
        if max_idle_clients < 1:
            raise ValueError("max_idle_clients must be positive")
        self._client_builder = client_builder or HttpIqaJobClient
        self._max_idle_clients = max_idle_clients
        self._idle: dict[str, IqaJobClient] = {}
        self._lock = Lock()
        self._closed = False
        self._clients_created = 0
        self._leases_reused = 0
        self._active_leases = 0
        self._max_active_leases = 0
        self._discarded_clients = 0

    def client(self, base_url: str) -> IqaJobClient:
        endpoint = base_url.rstrip("/")
        with self._lock:
            if self._closed:
                raise RuntimeError("Remote IQA transport pool is closed")
            client = self._idle.pop(endpoint, None)
            if client is None:
                client = self._client_builder(endpoint)
                self._clients_created += 1
            else:
                self._leases_reused += 1
            self._active_leases += 1
            self._max_active_leases = max(self._max_active_leases, self._active_leases)
        return _ClientLease(self, endpoint, client)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            idle = tuple(self._idle.values())
            self._idle.clear()
        for client in idle:
            client.close()

    @property
    def diagnostics(self) -> IqaTransportPoolDiagnostics:
        with self._lock:
            return IqaTransportPoolDiagnostics(
                clients_created=self._clients_created,
                leases_reused=self._leases_reused,
                active_leases=self._active_leases,
                max_active_leases=self._max_active_leases,
                idle_clients=len(self._idle),
                discarded_clients=self._discarded_clients,
                closed=self._closed,
            )

    def _release(self, endpoint: str, client: IqaJobClient) -> None:
        keep = False
        with self._lock:
            self._active_leases = max(0, self._active_leases - 1)
            if (
                not self._closed
                and endpoint not in self._idle
                and len(self._idle) < self._max_idle_clients
            ):
                self._idle[endpoint] = client
                keep = True
            else:
                self._discarded_clients += 1
        if not keep:
            client.close()
