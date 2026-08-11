from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st


REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
WINDOW_MINUTES = 60
REFRESH_SECONDS = 30


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_recent_events(
    path: Path = LOG_PATH,
    *,
    now: datetime | None = None,
    window_minutes: int = WINDOW_MINUTES,
) -> list[dict[str, Any]]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current - timedelta(minutes=window_minutes)
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            item = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        timestamp = parse_timestamp(item.get("ts"))
        if timestamp is not None and cutoff <= timestamp <= current:
            item["_timestamp"] = timestamp
            events.append(item)
    return events


def dashboard_now() -> datetime:
    """Return current UTC time, with an optional timestamp for reproducible evidence."""
    override = parse_timestamp(os.getenv("DASHBOARD_AS_OF"))
    return override or datetime.now(timezone.utc)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    return float(pd.Series(values, dtype="float64").quantile(quantile))


def calculate_metrics(events: list[dict[str, Any]]) -> dict[str, Any]:
    requests = [item for item in events if item.get("event") == "request_received"]
    responses = [item for item in events if item.get("event") == "response_sent"]
    failures = [item for item in events if item.get("event") == "request_failed"]

    latencies = [float(item.get("latency_ms", 0)) for item in responses]
    costs = [float(item.get("cost_usd", 0)) for item in responses]
    tokens_in = sum(int(item.get("tokens_in", 0)) for item in responses)
    tokens_out = sum(int(item.get("tokens_out", 0)) for item in responses)
    quality_values = [
        float(item["quality_score"])
        for item in responses
        if isinstance(item.get("quality_score"), (int, float))
    ]

    request_times = [item["_timestamp"] for item in requests if "_timestamp" in item]
    observed_minutes = 1.0
    if len(request_times) > 1:
        observed_minutes = max(
            (max(request_times) - min(request_times)).total_seconds() / 60,
            1.0,
        )

    error_breakdown = Counter(
        str(item.get("error_type", "UnknownError")) for item in failures
    )
    return {
        "latency_p50": percentile(latencies, 0.50),
        "latency_p95": percentile(latencies, 0.95),
        "latency_p99": percentile(latencies, 0.99),
        "request_count": len(requests),
        "requests_per_minute": len(requests) / observed_minutes,
        "error_rate_pct": (len(failures) / len(requests) * 100) if requests else 0.0,
        "error_breakdown": dict(sorted(error_breakdown.items())),
        "total_cost_usd": sum(costs),
        "tokens_in_total": tokens_in,
        "tokens_out_total": tokens_out,
        "tokens_total": tokens_in + tokens_out,
        "quality_avg": sum(quality_values) / len(quality_values) if quality_values else 0.0,
    }


def minute_series(events: list[dict[str, Any]], field: str) -> pd.DataFrame:
    rows = [
        {"minute": item["_timestamp"].replace(second=0, microsecond=0), "value": float(item.get(field, 0))}
        for item in events
        if item.get("event") == "response_sent" and "_timestamp" in item
    ]
    if not rows:
        return pd.DataFrame(columns=["minute", "value"])
    return pd.DataFrame(rows).groupby("minute", as_index=False)["value"].sum()


def slo_status(value: float, operator: str, threshold: float) -> str:
    passed = value <= threshold if operator == "lte" else value >= threshold
    return "✅ Đạt SLO" if passed else "🔴 Vi phạm SLO"


def metric_with_slo(label: str, value: str, status: str) -> None:
    st.metric(label, value)
    st.caption(status)


def render_rule_chart(data: pd.DataFrame, threshold: float, unit: str) -> None:
    if data.empty:
        st.info("Chưa có dữ liệu trong cửa sổ thời gian.")
        return
    line = alt.Chart(data).mark_line(point=True).encode(
        x=alt.X("minute:T", title="Thời gian (UTC)"),
        y=alt.Y("value:Q", title=unit),
        tooltip=[alt.Tooltip("minute:T"), alt.Tooltip("value:Q", format=".4f")],
    )
    rule = alt.Chart(pd.DataFrame({"threshold": [threshold]})).mark_rule(
        color="#e45756", strokeDash=[6, 4]
    ).encode(y="threshold:Q")
    st.altair_chart(line + rule, use_container_width=True)


def render_dashboard() -> None:
    current = dashboard_now()
    events = load_recent_events(now=current)
    metrics = calculate_metrics(events)
    responses = [item for item in events if item.get("event") == "response_sent"]

    st.title("Day 13 AI Observability")
    st.caption(
        f"Nguồn: data/logs.jsonl · Time range: {WINDOW_MINUTES} phút gần nhất · "
        f"Refresh: {REFRESH_SECONDS} giây · Cập nhật UTC: {current:%Y-%m-%d %H:%M:%S}"
    )

    left, right = st.columns(2)
    with left:
        st.subheader("1. Latency — P50 / P95 / P99")
        a, b, c = st.columns(3)
        a.metric("P50", f"{metrics['latency_p50']:.0f} ms")
        b.metric("P95", f"{metrics['latency_p95']:.0f} ms")
        c.metric("P99", f"{metrics['latency_p99']:.0f} ms")
        st.caption(f"SLO: P95 ≤ 3,000 ms · {slo_status(metrics['latency_p95'], 'lte', 3000)}")
        latency_df = pd.DataFrame(
            {
                "percentile": ["P50", "P95", "P99", "SLO"],
                "latency_ms": [metrics["latency_p50"], metrics["latency_p95"], metrics["latency_p99"], 3000],
            }
        )
        st.bar_chart(latency_df, x="percentile", y="latency_ms", horizontal=True)

    with right:
        st.subheader("2. Traffic — Request traffic")
        a, b = st.columns(2)
        a.metric("Tổng request", f"{metrics['request_count']:,}")
        b.metric("Request/phút", f"{metrics['requests_per_minute']:.2f} req/min")
        st.caption(f"SLO: ≥ 1 request/phút · {slo_status(metrics['requests_per_minute'], 'gte', 1)}")
        traffic_rows = [
            {"minute": item["_timestamp"].replace(second=0, microsecond=0), "requests": 1}
            for item in events
            if item.get("event") == "request_received" and "_timestamp" in item
        ]
        traffic_df = pd.DataFrame(traffic_rows)
        if not traffic_df.empty:
            traffic_df = traffic_df.groupby("minute", as_index=False)["requests"].sum()
            render_rule_chart(traffic_df.rename(columns={"requests": "value"}), 1, "requests/minute")
        else:
            st.info("Chưa có request trong cửa sổ thời gian.")

    left, right = st.columns(2)
    with left:
        st.subheader("3. Errors — Error rate & breakdown")
        metric_with_slo(
            "Error rate",
            f"{metrics['error_rate_pct']:.2f}%",
            f"SLO: ≤ 2% · {slo_status(metrics['error_rate_pct'], 'lte', 2)}",
        )
        breakdown = metrics["error_breakdown"]
        if breakdown:
            st.bar_chart(pd.DataFrame({"error_type": breakdown.keys(), "count": breakdown.values()}), x="error_type", y="count")
        else:
            st.success("Không có request_failed trong 60 phút gần nhất.")

    with right:
        st.subheader("4. Cost — Cost over time")
        metric_with_slo(
            "Tổng cost",
            f"${metrics['total_cost_usd']:.4f} USD",
            f"SLO: tổng cost ≤ $2.50 USD · {slo_status(metrics['total_cost_usd'], 'lte', 2.5)}",
        )
        render_rule_chart(minute_series(responses, "cost_usd"), 2.5, "USD/phút")

    left, right = st.columns(2)
    with left:
        st.subheader("5. Tokens — Input / Output")
        a, b = st.columns(2)
        a.metric("Input tokens", f"{metrics['tokens_in_total']:,}")
        b.metric("Output tokens", f"{metrics['tokens_out_total']:,}")
        st.caption(f"SLO: tổng ≤ 50,000 tokens · {slo_status(metrics['tokens_total'], 'lte', 50000)}")
        token_df = pd.DataFrame(
            {"type": ["Input", "Output", "SLO"], "tokens": [metrics["tokens_in_total"], metrics["tokens_out_total"], 50000]}
        )
        st.bar_chart(token_df, x="type", y="tokens", horizontal=True)

    with right:
        st.subheader("6. Quality — Quality proxy")
        metric_with_slo(
            "Quality trung bình",
            f"{metrics['quality_avg']:.3f} / 1.0",
            f"SLO: ≥ 0.75 · {slo_status(metrics['quality_avg'], 'gte', 0.75)}",
        )
        quality_df = pd.DataFrame(
            {"metric": ["Quality", "SLO"], "score": [metrics["quality_avg"], 0.75]}
        )
        st.bar_chart(quality_df, x="metric", y="score", horizontal=True)


def main() -> None:
    st.set_page_config(page_title="Day 13 Observability", page_icon="📊", layout="wide")

    @st.fragment(run_every=REFRESH_SECONDS)
    def auto_refresh_dashboard() -> None:
        render_dashboard()

    auto_refresh_dashboard()


if __name__ == "__main__":
    main()
