"""Async concurrency sweep to find the server's real saturation point.

Builds the exact production workload (1,200 child GETs) and replays it at a
range of concurrency levels using a single async event loop + HTTP/2, with
aggressive 429 re-enqueue (no backoff). Records throughput and 200-only
latency percentiles so we can see the knee: where p50 climbs while throughput
flattens (server-bound) vs throughput still rising (we were client-bound).
"""
import asyncio
import statistics
import time

import httpx

BASE = "https://hackathon.prod.pulsefoundry.ai"
FACILITIES = [101, 102, 103]
LEVELS = [64, 128, 192, 256, 384, 512]


async def get_until_ok(client, path, params, latencies, calls):
    """Retry until 200. Record latency of the successful 200 only."""
    while True:
        t = time.perf_counter()
        try:
            r = await client.get(path, params=params)
        except httpx.HTTPError:
            calls[0] += 1
            continue
        calls[0] += 1
        if r.status_code == 200:
            latencies.append(time.perf_counter() - t)
            return r.json()
        # 429 / 5xx: immediate re-enqueue (random 429 -> no backoff)


async def build_tasks(client):
    patients = []
    for fid in FACILITIES:
        rows = await get_until_ok(client, "/pcc/patients", {"facility_id": fid}, [], [0])
        patients.extend(rows)
    tasks = []
    for p in patients:
        tasks.append(("/pcc/diagnoses", {"patient_id": p["patient_id"]}))
        tasks.append(("/pcc/coverage", {"patient_id": p["patient_id"]}))
        tasks.append(("/pcc/notes", {"patient_id": p["id"]}))
        tasks.append(("/pcc/assessments", {"patient_id": p["id"]}))
    return tasks


async def run_level(tasks, conc):
    limits = httpx.Limits(max_connections=conc, max_keepalive_connections=conc,
                          keepalive_expiry=60)
    timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
    latencies, calls = [], [0]
    sem = asyncio.Semaphore(conc)
    async with httpx.AsyncClient(base_url=BASE, http2=True, limits=limits,
                                 timeout=timeout) as client:
        async def one(path, params):
            async with sem:
                return await get_until_ok(client, path, params, latencies, calls)
        t0 = time.perf_counter()
        await asyncio.gather(*(one(p, q) for p, q in tasks))
        dt = time.perf_counter() - t0
    lat = sorted(latencies)
    p50 = statistics.median(lat) * 1e3
    p95 = lat[int(0.95 * len(lat))] * 1e3
    return dt, calls[0], p50, p95


async def main():
    async with httpx.AsyncClient(base_url=BASE, http2=True,
                                 timeout=httpx.Timeout(30.0)) as c:
        tasks = await build_tasks(c)
    print(f"workload: {len(tasks)} child calls\n")
    print(f"{'conc':>5} {'wall':>7} {'calls':>6} {'thru/s':>8} "
          f"{'p50ms':>7} {'p95ms':>7}")
    for conc in LEVELS:
        dt, calls, p50, p95 = await run_level(tasks, conc)
        print(f"{conc:>5} {dt:>6.1f}s {calls:>6} {calls/dt:>8.0f} "
              f"{p50:>7.0f} {p95:>7.0f}")


if __name__ == "__main__":
    asyncio.run(main())
