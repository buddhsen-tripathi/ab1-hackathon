from __future__ import annotations

import csv
import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict

from billready.api.client import PCCClient
from billready.api.ingestion import ingest_all
from billready.config import OUTPUT_CSV
from billready.eligibility.routing import route_patient
from billready.models import EligibilityResult
from billready.storage.cache import CacheStore

logger = logging.getLogger(__name__)

CSV_FIELDS = [
    "patient_id",
    "internal_id",
    "facility_id",
    "first_name",
    "last_name",
    "is_new_admission",
    "has_active_mcb",
    "wound_type",
    "stage",
    "location",
    "length_cm",
    "width_cm",
    "depth_cm",
    "drainage_amount",
    "extraction_source",
    "extraction_confidence",
    "routing_decision",
    "reason",
    "submission_eligible",
    "missing_fields",
    "llm_check",
    "llm_check_note",
]


def write_csv(results: list[EligibilityResult], path=OUTPUT_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in results:
            row = asdict(result)
            row["missing_fields"] = ",".join(result.missing_fields)
            writer.writerow(row)


def print_summary(results: list[EligibilityResult], elapsed: float, stats: object) -> None:
    counts = {"auto_accept": 0, "flag_for_review": 0, "reject": 0}
    mcb_count = sum(1 for r in results if r.has_active_mcb)

    for r in results:
        counts[r.routing_decision] += 1

    print("\n" + "=" * 60)
    print("BillReady Pipeline — Run Summary")
    print("=" * 60)
    print(f"Patients processed:     {len(results)}")
    print(f"Active Medicare Part B: {mcb_count}")
    print(f"Auto accept:            {counts['auto_accept']}")
    print(f"Flag for review:        {counts['flag_for_review']}")
    print(f"Reject:                 {counts['reject']}")
    print(f"Runtime:                {elapsed:.1f}s")
    print(f"API requests:           {stats.total} (429s: {stats.rate_limited}, retries: {stats.retries})")
    print(f"Output CSV:             {OUTPUT_CSV}")
    print("=" * 60)

    print("\nSample auto_accept:")
    for r in results:
        if r.routing_decision == "auto_accept":
            print(f"  {r.patient_id} — {r.reason[:100]}...")
            break

    print("\nSample flag_for_review:")
    for r in results:
        if r.routing_decision == "flag_for_review":
            print(f"  {r.patient_id} — {r.reason[:100]}...")
            break

    print("\nSample reject:")
    for r in results:
        if r.routing_decision == "reject":
            print(f"  {r.patient_id} — {r.reason[:100]}...")
            break


async def run_pipeline(
    use_cache: bool = True,
    clear_cache: bool = False,
    llm_verify: bool = False,
    on_progress: Callable[[str, str, int], None] | None = None,
) -> list[EligibilityResult]:
    cache = CacheStore()
    if clear_cache:
        cache.clear_cache()
        logger.info("Cache cleared")
        if on_progress:
            on_progress("ingest", "Cache cleared — will fetch fresh data from API", 5)

    start = time.perf_counter()

    async with PCCClient() as client:
        store = cache if use_cache else _NoCache()
        records = await ingest_all(client, store, on_progress=on_progress)

        if on_progress:
            on_progress("extract", "Extracting wound fields and routing patients…", 78)

        records_by_id = {r.patient_id: r for r in records}
        results = [route_patient(record) for record in records]

        if on_progress:
            on_progress("extract", f"Routed {len(results)} patients", 85)

        if llm_verify:
            from billready.eligibility.llm_verify import suggest_for_review

            if on_progress:
                on_progress("llm", "LLM suggestions for Needs Review cases (batched)…", 88)
            logger.info("Running batched LLM suggestions on flag_for_review cases...")

            def llm_progress(message: str, done: int, total: int) -> None:
                if on_progress:
                    pct = 88 + int(4 * done / max(total, 1))
                    on_progress("llm", message, pct)

            results, llm_stats = suggest_for_review(
                results, records_by_id, on_progress=llm_progress
            )
            if on_progress:
                on_progress(
                    "llm",
                    (
                        f"LLM suggestions — {llm_stats['calls']} API call(s), "
                        f"{llm_stats['suggestions']} patients"
                    ),
                    92,
                )
        else:
            llm_stats = {"calls": 0, "suggestions": 0, "skipped": 0}

        if on_progress:
            on_progress("save", "Saving eligibility results to database…", 95)

        cache.save_eligibility_results([asdict(r) for r in results])
        write_csv(results)

        elapsed = time.perf_counter() - start
        run_stats = {
            "elapsed_seconds": round(elapsed, 2),
            "patients": len(results),
            "auto_accept": sum(1 for r in results if r.routing_decision == "auto_accept"),
            "flag_for_review": sum(1 for r in results if r.routing_decision == "flag_for_review"),
            "reject": sum(1 for r in results if r.routing_decision == "reject"),
            "api_requests": client.stats.total,
            "rate_limited": client.stats.rate_limited,
            "retries": client.stats.retries,
            "llm_calls": llm_stats["calls"],
            "llm_suggestions": llm_stats["suggestions"],
        }
        cache.set_meta("last_pipeline_run", json.dumps(run_stats))
        print_summary(results, elapsed, client.stats)

    return results


class _NoCache:
    def get(self, key: str) -> None:
        return None

    def set(self, key: str, data: object) -> None:
        pass

    def set_meta(self, key: str, value: str) -> None:
        pass
