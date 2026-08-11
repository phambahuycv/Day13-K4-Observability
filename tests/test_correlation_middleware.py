from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import Request
from fastapi.testclient import TestClient

from app import logging_config
from app.agent import AgentResult
from app.main import agent, app, generic_exception_handler


def test_middleware_generates_correlation_id_and_timing_headers() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert re.fullmatch(r"req-[0-9a-f]{8}", response.headers["x-request-id"])
    assert float(response.headers["x-response-time-ms"]) >= 0


def test_middleware_preserves_client_correlation_id() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"x-request-id": "req-client01"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-client01"


def test_chat_logs_share_correlation_id_and_enriched_context(
    monkeypatch, tmp_path: Path
) -> None:
    log_path = tmp_path / "logs.jsonl"
    monkeypatch.setattr(logging_config, "LOG_PATH", log_path)
    monkeypatch.setattr(
        agent,
        "run",
        lambda **_: AgentResult(
            answer="Test answer",
            latency_ms=12,
            tokens_in=10,
            tokens_out=20,
            cost_usd=0.001,
            quality_score=0.9,
        ),
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            headers={"x-request-id": "req-context1"},
            json={
                "user_id": "student-01",
                "session_id": "session-01",
                "feature": "qa",
                "message": "Explain observability",
            },
        )

    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    api_records = [record for record in records if record.get("service") == "api"]

    assert response.status_code == 200
    assert response.json()["correlation_id"] == "req-context1"
    assert len(api_records) == 2
    for record in api_records:
        assert record["correlation_id"] == "req-context1"
        assert record["user_id_hash"] != "student-01"
        assert record["session_id"] == "session-01"
        assert record["feature"] == "qa"
        assert record["model"] == "claude-sonnet-4-5"
        assert record["env"] == "dev"


def test_generic_exception_handler_returns_correlation_id() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/"})
    request.state.correlation_id = "req-error001"

    response = asyncio.run(generic_exception_handler(request, RuntimeError("boom")))

    assert response.status_code == 500
    assert response.headers["x-request-id"] == "req-error001"
