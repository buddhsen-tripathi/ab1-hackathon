from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

from billready.config import BASE_URL, MAX_CONCURRENT_REQUESTS, MAX_RETRIES

logger = logging.getLogger(__name__)


@dataclass
class RequestStats:
    total: int = 0
    success: int = 0
    rate_limited: int = 0
    retries: int = 0
    errors: int = 0


@dataclass
class PCCClient:
    base_url: str = BASE_URL
    max_concurrent: int = MAX_CONCURRENT_REQUESTS
    max_retries: int = MAX_RETRIES
    stats: RequestStats = field(default_factory=RequestStats)
    _semaphore: asyncio.Semaphore | None = field(default=None, repr=False)
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def __aenter__(self) -> PCCClient:
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        self._client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()

    async def get_json(self, path: str, params: dict | None = None) -> list | dict:
        assert self._client and self._semaphore

        async with self._semaphore:
            for attempt in range(self.max_retries):
                self.stats.total += 1
                try:
                    response = await self._client.get(path, params=params)
                except httpx.HTTPError as exc:
                    self.stats.errors += 1
                    wait = min(2**attempt, 10)
                    logger.warning("HTTP error on %s: %s — retry in %ss", path, exc, wait)
                    await asyncio.sleep(wait)
                    self.stats.retries += 1
                    continue

                if response.status_code == 429:
                    self.stats.rate_limited += 1
                    self.stats.retries += 1
                    wait = int(response.headers.get("Retry-After", "2"))
                    logger.debug("429 on %s — waiting %ss", path, wait)
                    await asyncio.sleep(wait)
                    continue

                if response.status_code >= 500:
                    self.stats.errors += 1
                    self.stats.retries += 1
                    wait = min(2**attempt, 10)
                    logger.warning("Server %s on %s — retry in %ss", response.status_code, path, wait)
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                self.stats.success += 1
                return response.json()

            raise RuntimeError(f"Failed after {self.max_retries} attempts: {path} {params}")
