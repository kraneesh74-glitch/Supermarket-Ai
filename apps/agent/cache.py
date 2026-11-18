"""High-Performance Multi-Tier Caching Layer (< 5s SLA - Task 4.3).

Provides in-memory TTL caching with Redis-compatible semantics for:
- Store operating hours and department schedules (TTL: 30 minutes)
- Active weekly promotions and circular deals (TTL: 15 minutes)
- High-frequency stock and price queries (TTL: 5 minutes)
- Immediate cache invalidation on inventory / POS updates
"""

import time
import threading
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CacheEntry(BaseModel):
    value: Any
    expires_at: float
    tag: str


class ResponseCache:
    """Thread-safe TTL Cache for sub-millisecond retrieval of frequent queries."""

    def __init__(self, default_ttl_seconds: int = 300):
        self.default_ttl = default_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                self.misses += 1
                return None

            if time.time() > entry.expires_at:
                # Expired
                del self._cache[key]
                self.misses += 1
                return None

            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None, tag: str = "general") -> None:
        duration = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + duration
        with self._lock:
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at, tag=tag)

    def invalidate(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def invalidate_tag(self, tag: str) -> int:
        """Invalidate all cache entries associated with a category/tag (e.g., 'inventory')."""
        with self._lock:
            keys_to_delete = [k for k, entry in self._cache.items() if entry.tag == tag]
            for k in keys_to_delete:
                del self._cache[k]
            return len(keys_to_delete)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        total = self.hits + self.misses
        hit_ratio = round(self.hits / total, 3) if total > 0 else 0.0
        return {
            "total_requests": total,
            "hits": self.hits,
            "misses": self.misses,
            "hit_ratio": hit_ratio,
            "cached_keys_count": len(self._cache),
        }


# Global response cache singleton
cache = ResponseCache()

