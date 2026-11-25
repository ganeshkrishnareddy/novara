#!/usr/bin/env python3
"""Small, honest local latency probe for NOVARA read endpoints.

This is NOT a load test. It measures sequential requests against one local
uvicorn process and one local SQLite file, with no concurrency, no external
network and no production-like data. Results describe this workstation only.

Usage:
    python scripts/performance_probe.py [base_url] [iterations]
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from urllib.request import Request, urlopen

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
ITERATIONS = int(sys.argv[2]) if len(sys.argv) > 2 else 20
EMAIL = os.getenv("NOVARA_PERF_EMAIL", "qa.owner@example.com")
PASSWORD = os.getenv("NOVARA_PERF_PASSWORD", "Password123!")


def call(path: str, token: str | None = None, body: dict | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        import json

        data = json.dumps(body).encode()
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(BASE + path, data=data, headers=headers, method="POST" if data else "GET")
    started = time.perf_counter()
    with urlopen(request, timeout=10) as response:
        payload = response.read().decode()
        status = response.status
    return (time.perf_counter() - started) * 1000, status, payload


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def main() -> int:
    _, status, payload = call(
        "/api/v1/auth/login", body={"email": EMAIL, "password": PASSWORD}
    )
    if status != 200:
        print(f"login failed: {status} {payload[:200]}")
        return 1
    import json

    session = json.loads(payload)
    token = session["access_token"]
    wid = session["workspace_id"]
    root = f"/api/v1/workspaces/{wid}"

    endpoints = [
        ("health", "/health"),
        ("contacts", root + "/contacts"),
        ("leads", root + "/leads"),
        ("tasks", root + "/tasks"),
        ("events", root + "/events?limit=100"),
        ("operations summary", root + "/operations/summary"),
        ("BI funnel", root + "/analytics/funnel"),
        ("event volume", root + "/analytics/events/volume"),
        ("job stats", root + "/jobs/stats"),
        ("adapter catalog", root + "/adapters"),
    ]

    print(f"base_url: {BASE}")
    print(f"iterations_per_endpoint: {ITERATIONS}")
    print(f"workspace: {session.get('workspace_name', wid)}")
    print("conditions: local uvicorn, single process, SQLite, sequential requests, no external calls")
    print("")
    print(f"{'endpoint':22} {'median_ms':>10} {'p95_ms':>9} {'min_ms':>9} {'max_ms':>9} {'status':>7}")
    for label, path in endpoints:
        call(path, token)  # one warm-up request
        samples = []
        last_status = 0
        for _ in range(ITERATIONS):
            elapsed, last_status, _ = call(path, token)
            samples.append(elapsed)
        print(
            f"{label:22} {statistics.median(samples):10.2f} "
            f"{percentile(samples, 0.95):9.2f} {min(samples):9.2f} "
            f"{max(samples):9.2f} {last_status:7}"
        )
    print("")
    print("Not a load test. No throughput or concurrency claim is made.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
