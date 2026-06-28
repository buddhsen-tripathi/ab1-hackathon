"""Coverage filter — active Medicare Part B.

Gate on payer_code == 'MCB' (payer_type lumps MCB/MCA/MCD all as 'Medicare',
so it can't distinguish Part B). Active = no end date, or end date in future.
"""
from datetime import datetime, timezone


def has_active_mcb(coverage_records) -> bool:
    now = datetime.now(timezone.utc)
    for rec in coverage_records or []:
        payer_code = (rec.get("payer_code") or "").upper()
        payer_type = (rec.get("payer_type") or "").lower()
        if payer_code != "MCB" and "medicare b" not in payer_type:
            continue

        effective_to = rec.get("effective_to")
        if not effective_to:
            return True
        try:
            end = datetime.fromisoformat(str(effective_to).replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
            if end >= now:
                return True
        except ValueError:
            continue
    return False
