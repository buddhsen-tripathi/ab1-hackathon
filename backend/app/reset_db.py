"""Empty the database for a clean test run.

Tables fall into classes with different reset semantics:
  source    patients/diagnoses/coverage/notes/assessments  re-fetched by `ingest`
  derived   wound_extractions/patient_eligibility           rebuilt by preprocess/eligibility
  kb_cache  kb_extractions/kb_patterns                       memoization; masks parser code changes
  kb_know   kb_abbreviations/kb_lexicon                      LEARNED knowledge — preserved by default

Default wipes source + derived + kb_cache and PRESERVES learned knowledge, so a
reset doesn't make the LLM re-discover abbreviations it already learned. The
extraction cache IS cleared because it would otherwise serve stale results and
mask parser code changes. Use --all to also wipe the learned KB (e.g. after a
KB schema change or to re-test the learning loop from scratch).

Usage:
    python -m app.reset_db          # source + derived + kb cache (asks to confirm)
    python -m app.reset_db --yes    # same, no prompt
    python -m app.reset_db --all    # also wipe learned KB knowledge
    python -m app.reset_db --all -y

Re-ingest afterwards with: python -m app.ingest
"""
import sys

from . import db

SOURCE = list(db.TABLES)
DERIVED = ["wound_extractions", "patient_eligibility"]
KB_CACHE = ["kb_extractions", "kb_patterns"]
KB_KNOWLEDGE = ["kb_abbreviations", "kb_lexicon"]


def _existing(conn, names):
    """Keep only tables that exist — some are created only by later stages."""
    out = []
    with conn.cursor() as cur:
        for n in names:
            cur.execute("SELECT to_regclass(%s) AS t", (f"public.{n}",))
            if cur.fetchone()["t"] is not None:
                out.append(n)
    return out


def _counts(conn, names):
    out = {}
    with conn.cursor() as cur:
        for n in names:
            cur.execute(f"SELECT COUNT(*) AS c FROM {n}")
            out[n] = cur.fetchone()["c"]
    return out


def _truncate(conn, names):
    if not names:
        return
    with conn.cursor() as cur:
        cur.execute("TRUNCATE " + ", ".join(names) + " RESTART IDENTITY")
    conn.commit()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    assume_yes = "--yes" in argv or "-y" in argv
    wipe_all = "--all" in argv

    targets = SOURCE + DERIVED + KB_CACHE + (KB_KNOWLEDGE if wipe_all else [])

    with db.connect() as conn:
        targets = _existing(conn, targets)
        counts = _counts(conn, targets)
        total = sum(counts.values())
        print("will wipe:", counts, f"(total {total} rows)")

        if not wipe_all:
            preserved = _existing(conn, KB_KNOWLEDGE)
            if preserved:
                print("preserving learned KB:", _counts(conn, preserved),
                      "— use --all to wipe")

        if total == 0:
            print("already empty — nothing to do.")
            return 0

        if not assume_yes:
            ans = input(f"Truncate {len(targets)} tables? [y/N] ").strip().lower()
            if ans not in ("y", "yes"):
                print("aborted.")
                return 1

        _truncate(conn, targets)
        print(f"removed {total} rows. now:", _counts(conn, targets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
