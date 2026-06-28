from __future__ import annotations

from datetime import datetime, timezone


def has_active_mcb(coverage_records: list[dict]) -> bool:
    """Return True if patient has active Medicare Part B coverage."""
    now = datetime.now(timezone.utc)

    for record in coverage_records:
        payer_code = (record.get("payer_code") or "").upper()
        payer_type = (record.get("payer_type") or "").lower()

        is_mcb = payer_code == "MCB" or "medicare b" in payer_type or payer_type == "medicare b"
        if not is_mcb:
            continue

        effective_to = record.get("effective_to")
        if effective_to is None:
            return True

        try:
            end = datetime.fromisoformat(effective_to.replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end >= now:
                return True
        except ValueError:
            continue

    return False
