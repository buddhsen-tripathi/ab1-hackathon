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
import threading

from .config import OPENROUTER_MODEL
from .preprocess.schema import BLOCKING_FLAGS

ENABLED = False

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
    """Confidence gate: escalate only when the LLM can plausibly add value —
    there's unstructured text AND the heuristic result is uncertain."""
    text = doc.get("note_text") or doc.get("raw_json")
    if not text or primary is None:
        return False
    if primary.billing_ready and primary.confidence >= 0.75:
        return False                              # already clean — don't pay
    if primary.confidence < 0.75:
        return True
    if any(f in BLOCKING_FLAGS for f in primary.flags):
        return True
    return primary.source_format in HARD_FORMATS


def escalate(doc, partial):
    """Resolve a hard extraction against the raw text. Returns an enrichment
    dict (see module docstring) or None when nothing was added / stub disabled."""
    if not ENABLED:
        return None
    # TODO: OpenRouter call (config.OPENROUTER_MODEL), strict-JSON response.
    return None
