"""Self-growing knowledge base (Neon Postgres).

The pipeline reads this on the hot parse path and writes back to it whenever
the LLM escalation layer (or a human) resolves something new — so over time
more is handled by cheap deterministic lookups and the LLM fires less.

Tables
  kb_abbreviations  surface -> expansion            feeds normalize.expand_abbreviations
  kb_lexicon        (category, surface) -> canonical drainage / wound_type / ... synonyms
  kb_extractions    note signature -> parsed rows    memoization (skip re-parsing/LLM)
  kb_patterns       (dimension,key,metric) -> value  rolled-up "what's missing where"

Connecting to Neon is slow, so a run loads the small tables into memory ONCE,
parses against the in-memory copy on the hot path, and flushes new knowledge in
a single batch at the end. The module-level dicts are the live read cache that
normalize.py consults — seeded at import so expansion works even with no DB.
"""
import hashlib
import re
from collections import defaultdict

from psycopg.types.json import Jsonb

from .db import connect

# --- schema ---------------------------------------------------------------

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS kb_abbreviations (
        surface     TEXT PRIMARY KEY,
        expansion   TEXT NOT NULL,
        category    TEXT,
        source      TEXT DEFAULT 'seed',
        hits        INTEGER DEFAULT 0,
        created_at  TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS kb_lexicon (
        category    TEXT NOT NULL,
        surface     TEXT NOT NULL,
        canonical   TEXT NOT NULL,
        source      TEXT DEFAULT 'seed',
        hits        INTEGER DEFAULT 0,
        PRIMARY KEY (category, surface)
    )""",
    """CREATE TABLE IF NOT EXISTS kb_extractions (
        signature   TEXT PRIMARY KEY,
        fields      JSONB NOT NULL,
        method      TEXT,
        confidence  REAL,
        hits        INTEGER DEFAULT 0,
        created_at  TIMESTAMPTZ DEFAULT now()
    )""",
    """CREATE TABLE IF NOT EXISTS kb_patterns (
        dimension   TEXT NOT NULL,
        key         TEXT NOT NULL,
        metric      TEXT NOT NULL,
        value       REAL,
        n           INTEGER,
        updated_at  TIMESTAMPTZ DEFAULT now(),
        PRIMARY KEY (dimension, key, metric)
    )""",
]

# --- seeds (plain surface forms; patterns built at use) -------------------
# Moved here from normalize.py: this module is now the single source of truth
# for the abbreviation seam the parsers expand against.
SEED_ABBREVIATIONS = {
    "aprx": "approx", "approx.": "approx", "pt": "patient", "w/": "with",
    "s/p": "status post", "meas": "measures", "c/o": "complains of",
    "wnl": "within normal limits",
    # wound-care shorthand
    "ssi": "surgical site infection", "dti": "deep tissue injury",
    "pu": "pressure ulcer", "dfu": "diabetic foot ulcer",
    "vlu": "venous leg ulcer", "serosang": "serosanguineous",
    "sang": "sanguineous",
}

# Learned drainage/type synonyms live here; seeded empty so normalize.py's
# built-in maps stay authoritative until the LLM teaches us something new.
SEED_LEXICON = {}

# --- live in-memory read cache (what normalize.py consults) ---------------
_ABBREV = dict(SEED_ABBREVIATIONS)
_LEXICON = dict(SEED_LEXICON)
_CACHE = {}            # signature -> list[row dict]
_abbrev_re = None      # compiled alternation, rebuilt when _ABBREV changes

# pending writes accumulated during a run, flushed once at the end
_new_abbrev = {}
_new_lexicon = {}
_new_extractions = {}


# --- abbreviation expansion (the seam) ------------------------------------

def _recompile():
    global _abbrev_re
    if not _ABBREV:
        _abbrev_re = None
        return
    # longest surface first so 'approx.' wins over 'approx', etc.
    surfaces = sorted(_ABBREV, key=len, reverse=True)
    _abbrev_re = re.compile(
        r"(?<![A-Za-z])(" + "|".join(re.escape(s) for s in surfaces) + r")(?![A-Za-z])",
        re.IGNORECASE,
    )


def expand(text):
    """Expand known shorthand. Reads the live in-memory map (no DB)."""
    if not text or not _ABBREV:
        return text or ""
    if _abbrev_re is None:
        _recompile()
    return _abbrev_re.sub(lambda m: _ABBREV.get(m.group(1).lower(), m.group(1)), text)


def abbreviations():
    return _ABBREV


def lexicon_lookup(category, text):
    """Fallback for normalize.py: scan text for a learned synonym of `category`."""
    if not text or not _LEXICON:
        return None
    low = text.lower()
    for (cat, surface), canonical in _LEXICON.items():
        if cat == category and re.search(
            rf"(?<![A-Za-z]){re.escape(surface)}(?![A-Za-z])", low
        ):
            return canonical
    return None


# --- signatures + memoization cache ---------------------------------------

def signature(text):
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def cache_get(sig):
    if sig in _new_extractions:
        return _new_extractions[sig]["fields"]
    return _CACHE.get(sig)


def cache_put(sig, rows, method=None, confidence=None):
    _new_extractions[sig] = {"fields": rows, "method": method, "confidence": confidence}
    _CACHE[sig] = rows


def restamp(rows, doc):
    """Re-attach the current doc's identity to cached field rows (cached by
    text signature, so the same text under another patient stays correct)."""
    out = []
    for r in rows:
        c = dict(r)
        c["patient_id"] = doc["patient_id"]
        c["source_doc_id"] = doc["id"]
        out.append(c)
    return out


# --- learning (queued in memory, flushed at end of run) -------------------

def learn_abbreviation(surface, expansion, category=None, source="llm"):
    surface = (surface or "").strip().lower()
    expansion = (expansion or "").strip()
    if not surface or not expansion or surface in _ABBREV:  # both columns are NOT NULL
        return
    _ABBREV[surface] = expansion
    _new_abbrev[surface] = (expansion, category, source)
    _recompile()


def learn_lexicon(category, surface, canonical, source="llm"):
    category = (category or "").strip()
    surface = (surface or "").strip().lower()
    canonical = (canonical or "").strip()
    if not category or not surface or not canonical:  # all three are NOT NULL
        return
    key = (category, surface)
    if key in _LEXICON:
        return
    _LEXICON[key] = canonical
    _new_lexicon[key] = (canonical, source)


def learn_from(enrichment):
    """Absorb an LLM escalation result's learned artifacts into the KB.

    The model occasionally emits partial rows (null expansion/canonical, "n/a"
    surface); the learn_* helpers drop those so the flush never hits a NOT NULL.
    """
    for a in (enrichment or {}).get("abbreviations") or []:
        if isinstance(a, dict):
            learn_abbreviation(a.get("surface"), a.get("expansion"), a.get("category"))
    for l in (enrichment or {}).get("lexicon") or []:
        if isinstance(l, dict):
            learn_lexicon(l.get("category"), l.get("surface"), l.get("canonical"))


# --- DB lifecycle ---------------------------------------------------------

def _with(conn, fn):
    if conn is not None:
        return fn(conn)
    with connect() as c:
        return fn(c)


def init(conn=None):
    def _do(c):
        with c.cursor() as cur:
            for stmt in SCHEMA:
                cur.execute(stmt)
        c.commit()
    return _with(conn, _do)


def seed(conn=None):
    """Idempotently load the seed abbreviations into the table."""
    def _do(c):
        with c.cursor() as cur:
            cur.executemany(
                """INSERT INTO kb_abbreviations (surface, expansion, source)
                   VALUES (%s,%s,'seed') ON CONFLICT (surface) DO NOTHING""",
                [(s, e) for s, e in SEED_ABBREVIATIONS.items()],
            )
        c.commit()
    return _with(conn, _do)


def load(conn=None):
    """Pull abbreviations, lexicon and the extraction cache into memory."""
    def _do(c):
        with c.cursor() as cur:
            cur.execute("SELECT surface, expansion FROM kb_abbreviations")
            for r in cur.fetchall():
                _ABBREV[r["surface"]] = r["expansion"]
            cur.execute("SELECT category, surface, canonical FROM kb_lexicon")
            for r in cur.fetchall():
                _LEXICON[(r["category"], r["surface"])] = r["canonical"]
            cur.execute("SELECT signature, fields FROM kb_extractions")
            for r in cur.fetchall():
                _CACHE[r["signature"]] = r["fields"]
        _recompile()
        return {"abbreviations": len(_ABBREV), "lexicon": len(_LEXICON),
                "cached_docs": len(_CACHE)}
    return _with(conn, _do)


def flush(conn=None):
    """Persist everything learned/cached this run in one batch."""
    def _do(c):
        with c.cursor() as cur:
            if _new_abbrev:
                cur.executemany(
                    """INSERT INTO kb_abbreviations (surface, expansion, category, source, hits)
                       VALUES (%s,%s,%s,%s,1)
                       ON CONFLICT (surface) DO UPDATE SET hits = kb_abbreviations.hits + 1""",
                    [(s, e, cat, src) for s, (e, cat, src) in _new_abbrev.items()],
                )
            if _new_lexicon:
                cur.executemany(
                    """INSERT INTO kb_lexicon (category, surface, canonical, source, hits)
                       VALUES (%s,%s,%s,%s,1)
                       ON CONFLICT (category, surface) DO UPDATE SET hits = kb_lexicon.hits + 1""",
                    [(cat, s, canon, src) for (cat, s), (canon, src) in _new_lexicon.items()],
                )
            if _new_extractions:
                cur.executemany(
                    """INSERT INTO kb_extractions (signature, fields, method, confidence)
                       VALUES (%s,%s,%s,%s)
                       ON CONFLICT (signature) DO UPDATE SET hits = kb_extractions.hits + 1""",
                    [(sig, Jsonb(v["fields"]), v["method"], v["confidence"])
                     for sig, v in _new_extractions.items()],
                )
        c.commit()
        written = {"abbreviations": len(_new_abbrev), "lexicon": len(_new_lexicon),
                   "extractions": len(_new_extractions)}
        _new_abbrev.clear(); _new_lexicon.clear(); _new_extractions.clear()
        return written
    return _with(conn, _do)


def record_patterns(rows, conn=None):
    """Roll up per-format coverage/quality so we can see what's missing where."""
    by_fmt = defaultdict(list)
    for r in rows:
        if r.get("is_primary", True):
            by_fmt[r.get("source_format", "unknown")].append(r)

    metrics = []
    for fmt, rs in by_fmt.items():
        n = len(rs)
        def rate(pred):
            return round(sum(1 for r in rs if pred(r)) / n, 3)
        metrics.extend([
            ("format", fmt, "n", float(n), n),
            ("format", fmt, "wound_type_coverage", rate(lambda r: r.get("wound_type")), n),
            ("format", fmt, "depth_coverage", rate(lambda r: r.get("depth_cm") is not None), n),
            ("format", fmt, "drainage_coverage", rate(lambda r: r.get("drainage_amount")), n),
            ("format", fmt, "billing_ready_rate", rate(lambda r: r.get("billing_ready")), n),
            ("format", fmt, "avg_confidence",
             round(sum(r.get("confidence", 0) for r in rs) / n, 3), n),
        ])

    def _do(c):
        with c.cursor() as cur:
            cur.executemany(
                """INSERT INTO kb_patterns (dimension, key, metric, value, n)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (dimension, key, metric)
                   DO UPDATE SET value = EXCLUDED.value, n = EXCLUDED.n,
                                 updated_at = now()""",
                metrics,
            )
        c.commit()
        return len(metrics)
    return _with(conn, _do)


def summary(conn=None):
    def _do(c):
        out = {}
        with c.cursor() as cur:
            for tbl in ("kb_abbreviations", "kb_lexicon", "kb_extractions", "kb_patterns"):
                cur.execute(f"SELECT COUNT(*) AS n FROM {tbl}")
                out[tbl] = cur.fetchone()["n"]
        return out
    return _with(conn, _do)
