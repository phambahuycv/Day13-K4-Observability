from datetime import datetime, timedelta, timezone
import json

import pytest

from scripts.dashboard_app import calculate_metrics, load_recent_events


def test_dashboard_filters_to_sixty_minutes_and_calculates_contract(tmp_path) -> None:
    now = datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    old = (now - timedelta(minutes=61)).isoformat().replace("+00:00", "Z")
    rows = [
        {"ts": old, "event": "request_received"},
        {"ts": recent, "event": "request_received"},
        {"ts": recent, "event": "request_received"},
        {"ts": recent, "event": "request_failed", "error_type": "RuntimeError"},
        {
            "ts": recent,
            "event": "response_sent",
            "latency_ms": 100,
            "cost_usd": 0.1,
            "tokens_in": 10,
            "tokens_out": 20,
            "quality_score": 0.8,
        },
    ]
    path = tmp_path / "logs.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    metrics = calculate_metrics(load_recent_events(path, now=now))

    assert metrics["request_count"] == 2
    assert metrics["error_rate_pct"] == 50
    assert metrics["error_breakdown"] == {"RuntimeError": 1}
    assert metrics["total_cost_usd"] == pytest.approx(0.1)
    assert metrics["tokens_in_total"] == 10
    assert metrics["tokens_out_total"] == 20
    assert metrics["quality_avg"] == pytest.approx(0.8)
