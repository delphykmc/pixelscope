from __future__ import annotations

import httpx

import pixelscope.remote.iqa_client as iqa_client
from pixelscope.remote.iqa_client import HttpIqaJobClient


def test_http_iqa_client_bypasses_environment_proxies_without_disabling_tls_env(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    real_client = httpx.Client

    def recording_client(*args, **kwargs):
        captured.update(kwargs)
        return real_client(*args, **kwargs)

    monkeypatch.setattr(iqa_client.httpx, "Client", recording_client)
    transport = httpx.MockTransport(lambda _request: httpx.Response(404))
    client = HttpIqaJobClient(
        "http://127.0.0.1:8001",
        transport=transport,
    )

    try:
        assert captured["proxies"] == {}
        assert captured["trust_env"] is True
        assert vars(client._client).get("_trust_env") is True
        assert client.proxy_policy == "direct"
    finally:
        client.close()
