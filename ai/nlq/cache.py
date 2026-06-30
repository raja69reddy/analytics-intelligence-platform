"""In-memory query cache for NLQ results."""
import time
from typing import Any, Optional


class QueryCache:
    """Dictionary-backed cache that stores question → SQL + result mappings."""

    def __init__(self):
        self._store: dict[str, dict] = {}
        self._hits = 0
        self._misses = 0
        self._total = 0

    def _key(self, question: str) -> str:
        return question.strip().lower()

    def cache_query(self, question: str, sql: str, result: Any) -> None:
        """Store a question, its generated SQL, and the query result."""
        self._store[self._key(question)] = {
            "question": question,
            "sql": sql,
            "result": result,
            "cached_at": time.time(),
        }

    def get_cached_query(self, question: str) -> Optional[dict]:
        """Return cached entry for question, or None on a miss."""
        self._total += 1
        entry = self._store.get(self._key(question))
        if entry:
            self._hits += 1
            return entry
        self._misses += 1
        return None

    def clear_cache(self) -> None:
        """Remove all cached entries and reset counters."""
        self._store.clear()
        self._hits = 0
        self._misses = 0
        self._total = 0

    def get_cache_stats(self) -> dict:
        """Return hit rate, total queries, and number of cached entries."""
        hit_rate = (self._hits / self._total * 100) if self._total > 0 else 0.0
        return {
            "total_queries": self._total,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round(hit_rate, 1),
            "cached_entries": len(self._store),
        }
