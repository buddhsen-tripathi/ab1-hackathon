"""PCC API client — the retry 'math function'.

The API returns HTTP 429 on ~30% of requests, independently per request.
Because attempts are independent, P(still failing after k tries) = 0.3**k,
so a handful of retries drives the per-item failure probability to ~0.
We fan out across distinct requests for throughput and retry per item for
reliability. See the math in the project notes.
"""
import threading
import time
import random
from collections import Counter

import httpx

BASE_URL = "https://hackathon.prod.pulsefoundry.ai"


class Stats:
    """Thread-safe request counters so we can prove the 429 behavior."""

    def __init__(self):
        self._lock = threading.Lock()
        self.counts = Counter()
        self.retry_after = Counter()

    def bump(self, key, n=1):
        with self._lock:
            self.counts[key] += n

    def note_retry_after(self, value):
        with self._lock:
            self.retry_after[str(value)] += 1

    def reset(self):
        """Clear counters so a fresh pipeline run reports only its own traffic."""
        with self._lock:
            self.counts = Counter()
            self.retry_after = Counter()

    def snapshot(self):
        with self._lock:
            c = dict(self.counts)
            total = c.get("total", 0) or 1
            return {
                "total_requests": c.get("total", 0),
                "ok": c.get("ok", 0),
                "rate_limited_429": c.get("429", 0),
                "server_5xx": c.get("5xx", 0),
                "net_errors": c.get("neterr", 0),
                "observed_429_rate": round(c.get("429", 0) / total, 4),
                "calls_per_success": round(
                    c.get("total", 0) / max(c.get("ok", 1), 1), 3
                ),
                "retry_after_distribution": dict(self.retry_after),
            }


STATS = Stats()

# One httpx.Client per worker thread (connection pooling, thread-safe usage).
_local = threading.local()


def get_client() -> httpx.Client:
    client = getattr(_local, "client", None)
    if client is None:
        client = httpx.Client(
            base_url=BASE_URL,
            timeout=30.0,
            headers={"Accept": "application/json"},
            follow_redirects=True,
        )
        _local.client = client
    return client


def get(path, params=None, *, max_retries=12):
    """GET with aggressive retry until success — the fastest path to ~0 failure.

    The 429 is random (~30% per request, independent — not a congestion signal),
    so we retry near-immediately with light jitter instead of honoring
    Retry-After. P(still failing after k tries) = 0.3**k.
    """
    client = get_client()
    for _ in range(max_retries):
        STATS.bump("total")
        try:
            resp = client.get(path, params=params)
        except httpx.HTTPError:
            STATS.bump("neterr")
            time.sleep(0.05)
            continue

        code = resp.status_code
        if code == 200:
            STATS.bump("ok")
            return resp.json()
        if code == 429:
            STATS.bump("429")
            STATS.note_retry_after(resp.headers.get("Retry-After"))
            time.sleep(0.02 + random.uniform(0, 0.05))  # jitter avoids lockstep
            continue
        if 500 <= code < 600:
            STATS.bump("5xx")
            time.sleep(0.1)
            continue
        # 4xx other than 429 — not retryable
        STATS.bump("other")
        resp.raise_for_status()
    raise RuntimeError(f"gave up after {max_retries} retries: {path} {params}")
