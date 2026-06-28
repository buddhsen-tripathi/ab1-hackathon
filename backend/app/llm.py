"""LLM escalation layer — the expensive specialist in the cascade.

Heuristics + the KB handle the confident majority for free. Only low-confidence,
hard-format, or conflicted extractions escalate here, where an LLM reads the RAW
text and returns (a) resolved wound fields and (b) reusable knowledge — new
abbreviations / synonyms — that gets written back to the KB so the same case is
handled cheaply next time. That write-back is what makes the pipeline get
faster as it runs.

Stubbed for now (ENABLED=False): returns None so the cascade is wired and its
selectivity is observable without spending OpenRouter calls. When enabled, the
call uses config.OPENROUTER_MODEL and must return strict JSON of the shape:

    {
      "fields": {"wound_type": "...", "depth_cm": 0.4, "drainage_amount": "...", ...},
      "abbreviations": [{"surface": "stg", "expansion": "stage", "category": null}],
      "lexicon": [{"category": "drainage_amount", "surface": "weeping", "canonical": "light"}],
      "confidence": 0.0-1.0
    }
"""
import json
import os
import re
import threading
import time

import httpx

from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL
from .preprocess.schema import BLOCKING_FLAGS

# On by default now that escalate() is implemented; set LLM_ENABLED=false to
# disable (e.g. to demo the cascade's selectivity without spending calls).
ENABLED = os.environ.get("LLM_ENABLED", "true").strip().lower() not in ("false", "0", "")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 30.0
# Bound a run: each call is ~4s, the cascade is sequential. 0 = unlimited.
# Set e.g. LLM_MAX_CALLS=50 for a quick demo warm-up; the KB cache makes the
# escalated docs free on the next run regardless.
MAX_CALLS = int(os.environ.get("LLM_MAX_CALLS", "0") or "0")
_CANON_TYPES = {
    "pressure_ulcer", "diabetic_foot_ulcer", "venous_ulcer", "arterial_ulcer",
    "surgical_site_infection", "abscess", "burn",
}
_DRAINAGE = {"none", "light", "moderate", "heavy"}

# Formats where the raw text carries signal a regex pass is likely to miss.
HARD_FORMATS = {"note_envive", "assessment_narrative", "note_shorthand", "unknown"}


class _LLMStats:
    """Thread-safe observability counters for the escalation layer."""

    def __init__(self):
        self._lock = threading.Lock()
        self.calls = 0
        self.errors = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_latency = 0.0

    def record(self, *, prompt_tokens=0, completion_tokens=0, latency=0.0, error=False):
        with self._lock:
            self.calls += 1
            if error:
                self.errors += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
            self.total_latency += latency

    def snapshot(self):
        with self._lock:
            return {
                "calls": self.calls,
                "errors": self.errors,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
                "avg_latency_s": round(self.total_latency / self.calls, 2) if self.calls else 0.0,
            }


STATS = _LLMStats()


def info():
    """Config + live stats for the LLM layer (drives the observability panel)."""
    return {
        "enabled": ENABLED,
        "model": OPENROUTER_MODEL,
        "hard_formats": sorted(HARD_FORMATS),
        "stats": STATS.snapshot(),
    }


def needs_escalation(doc, primary):
    """Confidence gate — the LLM is the *rare* specialist, not the default path.

    Escalate ONLY when the model can plausibly recover signal a regex pass
    missed: hard free-text formats whose heuristic parse came back thin, or an
    outright parse failure. We deliberately do NOT escalate for:
      - structured sources (already authoritative),
      - clean SOAP/structured regex parses (reliable enough),
      - fields that are simply ABSENT from the document — the model can't invent
        a depth that was never written, so "missing_depth" is a routing flag,
        not a reason to pay for a call.
    """
    text = doc.get("note_text") or doc.get("raw_json")
    if not text or primary is None:
        return False

    # Structured assessment fields are authoritative — never pay.
    if primary.method == "structured_field":
        return False

    flags = primary.flags or []
    if "unparseable" in flags:
        return True                               # nothing usable — let the LLM try

    # Only hard free-text formats benefit; structured/SOAP regex is reliable.
    if primary.source_format not in HARD_FORMATS:
        return False

    # ...and only when the heuristic clearly under-read the text (missed the
    # wound type or got no measurements at all, or is genuinely low-confidence).
    poor_yield = (
        primary.wound_type is None
        or (primary.length_cm is None and primary.width_cm is None)
        or (primary.confidence or 0.0) < 0.5
    )
    return poor_yield


_PROMPT = """You are a clinical wound-care data extractor. Read the RAW documentation \
and return STRICT JSON only — no prose, no markdown.

Extract these fields (use null if genuinely absent — never invent a value):
- wound_type: one of [pressure_ulcer, diabetic_foot_ulcer, venous_ulcer, arterial_ulcer, surgical_site_infection, abscess, burn] or null
- stage: "2" | "3" | "4" | "unstageable" (pressure ulcers only) or null
- location: anatomical site string or null
- length_cm, width_cm, depth_cm: numbers in cm or null
- drainage_amount: one of [none, light, moderate, heavy] or null

Also return the reusable knowledge you used to read shorthand, so it can be cached:
- abbreviations: list of {{"surface": "...", "expansion": "...", "category": null}}
- lexicon: list of {{"category": "drainage_amount", "surface": "weeping", "canonical": "light"}}
- confidence: number 0.0-1.0 (your overall confidence)

The heuristic pass already found (may be partial or null): {partial}
Only add what the heuristics missed; do not contradict confident values.

Return exactly:
{{"fields": {{...}}, "abbreviations": [...], "lexicon": [...], "confidence": 0.0}}

--- RAW DOCUMENTATION ---
{text}
"""


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _extract_json(content):
    content = (content or "").strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content).strip()
    try:
        return json.loads(content)
    except Exception:
        s, e = content.find("{"), content.rfind("}")
        if 0 <= s < e:
            try:
                return json.loads(content[s : e + 1])
            except Exception:
                return None
    return None


def _clean(parsed):
    """Validate/normalize the model output to the enrichment contract, or None."""
    if not isinstance(parsed, dict):
        return None
    raw = parsed.get("fields") or {}
    fields = {}
    if isinstance(raw, dict):
        wt = raw.get("wound_type")
        if isinstance(wt, str) and wt.lower().strip() in _CANON_TYPES:
            fields["wound_type"] = wt.lower().strip()
        st = raw.get("stage")
        if st not in (None, "", "null", "N/A"):
            fields["stage"] = str(st).replace("Stage", "").replace("stage", "").strip()
        loc = raw.get("location")
        if isinstance(loc, str) and loc.strip():
            fields["location"] = loc.strip()
        for k in ("length_cm", "width_cm", "depth_cm"):
            v = _num(raw.get(k))
            if v is not None and 0.1 <= v <= 60:
                fields[k] = v
        dr = raw.get("drainage_amount")
        if isinstance(dr, str) and dr.lower().strip() in _DRAINAGE:
            fields["drainage_amount"] = dr.lower().strip()

    abbreviations = parsed.get("abbreviations") if isinstance(parsed.get("abbreviations"), list) else []
    lexicon = parsed.get("lexicon") if isinstance(parsed.get("lexicon"), list) else []
    if not fields and not abbreviations and not lexicon:
        return None
    conf = _num(parsed.get("confidence")) or 0.0
    return {
        "fields": fields,
        "abbreviations": abbreviations,
        "lexicon": lexicon,
        "confidence": min(max(conf, 0.0), 1.0),
    }


def escalate(doc, partial):
    """Resolve a hard extraction against the raw text. Returns an enrichment
    dict (see module docstring) or None when nothing was added / disabled."""
    if not ENABLED or not OPENROUTER_API_KEY:
        return None
    if MAX_CALLS and STATS.calls >= MAX_CALLS:
        return None                               # run budget exhausted
    text = doc.get("note_text") or doc.get("raw_json")
    if not text:
        return None

    keys = ("wound_type", "stage", "location", "length_cm", "width_cm",
            "depth_cm", "drainage_amount")
    partial_summary = ", ".join(f"{k}={(partial or {}).get(k)}" for k in keys)
    prompt = _PROMPT.format(partial=partial_summary, text=str(text)[:2000])

    body = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "ABI Wound-Care Billing Pipeline",
    }

    t0 = time.time()
    try:
        resp = httpx.post(OPENROUTER_URL, json=body, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        STATS.record(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency=time.time() - t0,
        )
        return _clean(_extract_json(content))
    except Exception:
        STATS.record(latency=time.time() - t0, error=True)
        return None
