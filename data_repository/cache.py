"""Two-layer cache utilities for market data."""

from __future__ import annotations

import hashlib
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class CacheEntry:
    """Cached market data plus metadata."""

    history: pd.DataFrame
    provider: str
    saved_at: float


class MarketDataCache:
    """Memory + disk cache with per-request TTL."""

    _memory: dict[str, CacheEntry] = {}

    def __init__(self, cache_dir: Path, logger) -> None:
        self.cache_dir = cache_dir
        self.logger = logger
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, ttl_seconds: int) -> tuple[CacheEntry | None, str | None]:
        """Return cache entry and cache layer if still fresh."""

        now = time.time()
        entry = self._memory.get(key)
        if entry and now - entry.saved_at <= ttl_seconds:
            self.logger.info("cache hit memory key=%s ttl=%s", key, ttl_seconds)
            return entry, "memory"

        path = self._path_for(key)
        if not path.exists():
            self.logger.info("cache miss key=%s", key)
            return None, None

        try:
            with path.open("rb") as handle:
                entry = pickle.load(handle)
        except Exception as exc:
            self.logger.warning("cache read failed key=%s error=%s", key, exc)
            return None, None

        if now - entry.saved_at > ttl_seconds:
            self.logger.info("cache stale key=%s ttl=%s age=%.0f", key, ttl_seconds, now - entry.saved_at)
            return None, None

        self._memory[key] = entry
        self.logger.info("cache hit disk key=%s ttl=%s", key, ttl_seconds)
        return entry, "disk"

    def get_stale(self, key: str) -> CacheEntry | None:
        """Return any cached entry even when expired."""

        entry = self._memory.get(key)
        if entry:
            self.logger.info("cache stale memory fallback key=%s", key)
            return entry

        path = self._path_for(key)
        if not path.exists():
            return None

        try:
            with path.open("rb") as handle:
                entry = pickle.load(handle)
        except Exception as exc:
            self.logger.warning("stale cache read failed key=%s error=%s", key, exc)
            return None

        self._memory[key] = entry
        self.logger.info("cache stale disk fallback key=%s", key)
        return entry

    def set(self, key: str, history: pd.DataFrame, provider: str) -> None:
        """Persist a cache entry to memory and disk."""

        entry = CacheEntry(history=history.copy(), provider=provider, saved_at=time.time())
        self._memory[key] = entry
        try:
            with self._path_for(key).open("wb") as handle:
                pickle.dump(entry, handle)
            self.logger.info("cache write key=%s provider=%s rows=%s", key, provider, len(history))
        except Exception as exc:
            self.logger.warning("cache write failed key=%s error=%s", key, exc)

    def _path_for(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.pkl"
