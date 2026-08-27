from __future__ import annotations

import httpx

from pixelscope.remote.iqa_client import HttpIqaJobClient


def test_http_iqa_client_does_not_inherit_environment_proxy_settings() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(404))
    client = HttpIqaJobClient(
        "http://127.0.0.1:8001",
        transport=transport,
    )

    try:
        assert client._client._trust_env is False
    finally:
        client.close()
