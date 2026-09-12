"""Prometheus metrics registry for VoyagerAI.

Centralizes all custom Prometheus metric definitions. The prometheus-fastapi-
instrumentator handles default HTTP metrics (request count, latency, status);
this module adds LLM-specific and business-logic gauges/counters.

Usage in other modules:
    from metrics import (
        LLM_CALLS_TOTAL, LLM_TOKENS_TOTAL, LLM_COST_TOTAL,
        RATE_LIMIT_HITS_TOTAL, CIRCUIT_BREAKER_STATUS,
        DAILY_PLATFORM_SPEND, HOURLY_PLATFORM_SPEND, ACTIVE_SESSIONS,
    )
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# --- HTTP metrics (supplement the instrumentator's defaults) ---

HTTP_REQUESTS_TOTAL = Counter(
    "voyager_http_requests_total",
    "Total HTTP requests by method, path, and status.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "voyager_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# --- LLM metrics ---

LLM_CALLS_TOTAL = Counter(
    "voyager_llm_calls_total",
    "Total LLM API calls by model and subagent.",
    ["model", "subagent"],
)

LLM_TOKENS_TOTAL = Counter(
    "voyager_llm_tokens_total",
    "Total LLM tokens consumed by direction (input/output) and model.",
    ["model", "direction"],
)

LLM_COST_TOTAL = Counter(
    "voyager_llm_cost_usd_total",
    "Cumulative LLM cost in USD by model.",
    ["model"],
)

# --- Rate limiting & circuit breaker ---

RATE_LIMIT_HITS_TOTAL = Counter(
    "voyager_rate_limit_hits_total",
    "Total rate limit hits by endpoint type and identifier.",
    ["endpoint_type", "identifier"],
)

CIRCUIT_BREAKER_STATUS = Gauge(
    "voyager_circuit_breaker_status",
    "Circuit breaker status: 0 = closed (healthy), 1 = tripped (spend exceeded).",
)

# --- Platform spend gauges ---

DAILY_PLATFORM_SPEND = Gauge(
    "voyager_daily_platform_spend_usd",
    "Current daily platform-wide spend in USD.",
)

HOURLY_PLATFORM_SPEND = Gauge(
    "voyager_hourly_platform_spend_usd",
    "Current hourly platform-wide spend in USD.",
)

# --- Active sessions ---

ACTIVE_SESSIONS = Gauge(
    "voyager_active_sessions",
    "Number of currently active chat sessions.",
)
