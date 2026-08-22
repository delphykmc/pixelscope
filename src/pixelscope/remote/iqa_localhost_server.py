"""Debug-only real localhost HTTP server for exercising the P5-C client contract."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from typing import Any
from urllib.parse import urlsplit

LOCALHOST_SCENARIOS = (
    "normal",
    "partial",
    "failed",
    "cancelled",
    "create-500",
    "status-500",
    "result-500",
    "result-500-once",
    "malformed-json",
    "slow-status",
    "wrong-job-id",
    "wrong-schema",
)
MAX_REQUEST_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class LocalhostIqaServerConfig:
    """One deterministic fault scenario and logical published-result reference."""

    scenario: str = "normal"
    storage_root_id: str = "debug_iqa"
    result_relative_path: str = "results/job_debug_complete_manual1"
    last_request_path: Path | None = None
    slow_seconds: float = 35.0

    def __post_init__(self) -> None:
        if self.scenario not in LOCALHOST_SCENARIOS:
            raise ValueError(f"unsupported localhost IQA scenario: {self.scenario}")
        if not self.storage_root_id:
            raise ValueError("storage_root_id must not be empty")
        if not self.result_relative_path or self.result_relative_path.startswith(("/", "\\")):
            raise ValueError("result_relative_path must be relative")
        if self.slow_seconds < 0.0:
            raise ValueError("slow_seconds must be non-negative")


@dataclass
class _LocalJob:
    job_id: str
    total_scenes: int
    status_reads: int = 0
    result_reads: int = 0
    cancelled: bool = False


@dataclass(frozen=True)
class _ServerResponse:
    status: int
    payload: object | None = None
    raw: bytes | None = None
    content_type: str = "application/json"


class LocalhostIqaServer:
    """Stateful ThreadingHTTPServer facade used by scripts and real-socket tests."""

    def __init__(
        self,
        config: LocalhostIqaServerConfig,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
    ) -> None:
        self.config = config
        self._lock = Lock()
        self._jobs: dict[str, _LocalJob] = {}
        self._next_job = 1
        self._thread: Thread | None = None
        self._httpd = ThreadingHTTPServer((host, port), _LocalhostHandler)
        self._httpd.daemon_threads = True
        self._httpd.app = self  # type: ignore[attr-defined]

    @property
    def address(self) -> tuple[str, int]:
        host, port = self._httpd.server_address[:2]
        return str(host), int(port)

    @property
    def base_url(self) -> str:
        host, port = self.address
        return f"http://{host}:{port}"

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def close(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

    def __enter__(self) -> LocalhostIqaServer:
        self.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()

    def handle(self, method: str, target: str, body: bytes) -> _ServerResponse:
        path = urlsplit(target).path
        if method == "GET" and path == "/health":
            return _ServerResponse(200, {"status": "ok", "scenario": self.config.scenario})
        if method == "POST" and path == "/v1/iqa/jobs":
            return self._create(body)

        parts = tuple(part for part in path.split("/") if part)
        if len(parts) not in {4, 5} or parts[:3] != ("v1", "iqa", "jobs"):
            return _ServerResponse(404, {"detail": "not found"})
        job_id = parts[3]
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return _ServerResponse(404, {"detail": "unknown job"})
        if len(parts) == 4 and method == "GET":
            return self._status(job)
        if len(parts) == 5 and parts[4] == "result" and method == "GET":
            return self._result(job)
        if len(parts) == 5 and parts[4] == "cancel" and method == "POST":
            return self._cancel(job)
        return _ServerResponse(405, {"detail": "method not allowed"})

    def _create(self, body: bytes) -> _ServerResponse:
        if len(body) > MAX_REQUEST_BYTES:
            return _ServerResponse(413, {"detail": "request too large"})
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return _ServerResponse(400, {"detail": "invalid JSON"})
        if not isinstance(payload, dict):
            return _ServerResponse(400, {"detail": "request must be an object"})
        scenes = payload.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            return _ServerResponse(400, {"detail": "request must contain Scenes"})
        if self.config.scenario == "partial" and len(scenes) < 2:
            return _ServerResponse(400, {"detail": "partial scenario requires at least 2 Scenes"})
        self._capture_request(payload)
        if self.config.scenario == "create-500":
            return _ServerResponse(500, {"detail": "scripted create failure"})
        with self._lock:
            job_id = f"job_local_{self._next_job:06d}"
            self._next_job += 1
            self._jobs[job_id] = _LocalJob(job_id, len(scenes))
        return _ServerResponse(200, {"job_id": job_id, "state": "queued"})

    def _status(self, job: _LocalJob) -> _ServerResponse:
        if self.config.scenario == "status-500":
            return _ServerResponse(500, {"detail": "scripted status failure"})
        if self.config.scenario == "slow-status":
            time.sleep(self.config.slow_seconds)
        if self.config.scenario == "malformed-json":
            return _ServerResponse(200, raw=b"{", content_type="application/json")
        with self._lock:
            job.status_reads += 1
            status_reads = job.status_reads
            cancelled = job.cancelled
        returned_id = "wrong_job_id" if self.config.scenario == "wrong-job-id" else job.job_id
        if cancelled or self.config.scenario == "cancelled":
            return _ServerResponse(
                200,
                self._status_payload(returned_id, "cancelled", 0, job.total_scenes, "cancelled"),
            )
        if status_reads == 1:
            return _ServerResponse(
                200,
                self._status_payload(
                    returned_id,
                    "extracting",
                    0,
                    job.total_scenes,
                    "localhost mock extracting",
                ),
            )
        if self.config.scenario == "failed":
            return _ServerResponse(
                200,
                self._status_payload(returned_id, "failed", 0, job.total_scenes, "scripted failure"),
            )
        if self.config.scenario == "partial":
            completed = max(1, job.total_scenes - 1)
            return _ServerResponse(
                200,
                self._status_payload(
                    returned_id,
                    "partial",
                    completed,
                    job.total_scenes,
                    "scripted partial result",
                ),
            )
        return _ServerResponse(
            200,
            self._status_payload(
                returned_id,
                "succeeded",
                job.total_scenes,
                job.total_scenes,
                "localhost mock complete",
            ),
        )

    def _result(self, job: _LocalJob) -> _ServerResponse:
        with self._lock:
            job.result_reads += 1
            result_reads = job.result_reads
            status_reads = job.status_reads
        if status_reads < 2:
            return _ServerResponse(409, {"detail": "result is not published"})
        if self.config.scenario == "result-500":
            return _ServerResponse(500, {"detail": "scripted result failure"})
        if self.config.scenario == "result-500-once" and result_reads == 1:
            return _ServerResponse(500, {"detail": "scripted transient result failure"})
        if self.config.scenario in {"failed", "cancelled"} or job.cancelled:
            return _ServerResponse(409, {"detail": "terminal job has no result"})
        returned_id = "wrong_job_id" if self.config.scenario == "wrong-job-id" else job.job_id
        schema_version = 99 if self.config.scenario == "wrong-schema" else 2
        publication_state = "partial" if self.config.scenario == "partial" else "complete"
        return _ServerResponse(
            200,
            {
                "job_id": returned_id,
                "storage_root_id": self.config.storage_root_id,
                "relative_path": self.config.result_relative_path,
                "schema_version": schema_version,
                "publication_state": publication_state,
            },
        )

    def _cancel(self, job: _LocalJob) -> _ServerResponse:
        with self._lock:
            job.cancelled = True
        return _ServerResponse(
            200,
            self._status_payload(job.job_id, "cancelled", 0, job.total_scenes, "cancelled"),
        )

    def _capture_request(self, payload: dict[str, Any]) -> None:
        path = self.config.last_request_path
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + ".part")
        part.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        part.replace(path)

    @staticmethod
    def _status_payload(
        job_id: str,
        state: str,
        completed: int,
        total: int,
        message: str,
    ) -> dict[str, object]:
        return {
            "job_id": job_id,
            "state": state,
            "completed_scenes": completed,
            "total_scenes": total,
            "message": message,
        }


class _LocalhostHandler(BaseHTTPRequestHandler):
    server_version = "PixelScopeP5CMock/1"

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _dispatch(self, method: str) -> None:
        length_text = self.headers.get("Content-Length", "0")
        try:
            length = int(length_text)
        except ValueError:
            length = 0
        if length < 0 or length > MAX_REQUEST_BYTES:
            self._write(_ServerResponse(413, {"detail": "request too large"}))
            return
        body = self.rfile.read(length) if length else b""
        app = getattr(self.server, "app", None)
        if not isinstance(app, LocalhostIqaServer):
            self._write(_ServerResponse(500, {"detail": "server is not configured"}))
            return
        self._write(app.handle(method, self.path, body))

    def _write(self, response: _ServerResponse) -> None:
        if response.raw is not None:
            body = response.raw
        else:
            body = json.dumps(response.payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
