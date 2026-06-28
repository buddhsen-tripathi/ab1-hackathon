from __future__ import annotations

import asyncio
import json
import logging
import threading
import traceback
from datetime import datetime, timezone
from typing import Callable

from billready.pipeline import run_pipeline
from billready.storage.cache import CacheStore

logger = logging.getLogger(__name__)

ProgressFn = Callable[[str, str, int], None]

PIPELINE_STEPS = [
    {"id": "ingest", "label": "Ingest from PCC API"},
    {"id": "extract", "label": "Extract & route patients"},
    {"id": "llm", "label": "LLM suggestions"},
    {"id": "save", "label": "Save results"},
]


class PipelineJobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status: dict = self._idle_status()

    def _idle_status(self) -> dict:
        return {
            "state": "idle",
            "step": None,
            "message": "Ready",
            "progress": 0,
            "logs": [],
            "started_at": None,
            "finished_at": None,
            "error": None,
            "result": None,
        }

    def get_status(self) -> dict:
        with self._lock:
            status = dict(self._status)
            status["steps"] = PIPELINE_STEPS
            return status

    def start(
        self,
        *,
        clear_cache: bool = False,
        llm_verify: bool = False,
        use_cache: bool = True,
    ) -> dict:
        with self._lock:
            if self._status["state"] == "running":
                raise RuntimeError("Pipeline is already running")
            self._status = {
                **self._idle_status(),
                "state": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "message": "Starting pipeline…",
                "progress": 2,
                "logs": ["Pipeline started"],
            }

        thread = threading.Thread(
            target=self._run,
            kwargs={
                "clear_cache": clear_cache,
                "llm_verify": llm_verify,
                "use_cache": use_cache,
            },
            daemon=True,
        )
        thread.start()
        return self.get_status()

    def _append_log(self, message: str) -> None:
        with self._lock:
            self._status["logs"].append(message)
            if len(self._status["logs"]) > 80:
                self._status["logs"] = self._status["logs"][-80:]

    def _set_progress(self, step: str, message: str, progress: int) -> None:
        with self._lock:
            self._status["step"] = step
            self._status["message"] = message
            self._status["progress"] = min(progress, 99)
        self._append_log(message)

    def _run(
        self,
        *,
        clear_cache: bool,
        llm_verify: bool,
        use_cache: bool,
    ) -> None:
        def on_progress(step: str, message: str, progress: int) -> None:
            self._set_progress(step, message, progress)

        try:
            results = asyncio.run(
                run_pipeline(
                    use_cache=use_cache,
                    clear_cache=clear_cache,
                    llm_verify=llm_verify,
                    on_progress=on_progress,
                )
            )
            cache = CacheStore()
            run_meta = cache.get_meta("last_pipeline_run")
            result = json.loads(run_meta) if run_meta else {}

            with self._lock:
                self._status["state"] = "completed"
                self._status["step"] = "done"
                self._status["message"] = f"Done — {len(results)} patients processed"
                self._status["progress"] = 100
                self._status["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._status["result"] = result
            self._append_log(self._status["message"])
        except Exception as exc:
            logger.exception("Pipeline failed")
            with self._lock:
                self._status["state"] = "error"
                self._status["message"] = str(exc)
                self._status["error"] = traceback.format_exc()
                self._status["finished_at"] = datetime.now(timezone.utc).isoformat()
            self._append_log(f"Error: {exc}")


pipeline_jobs = PipelineJobManager()
