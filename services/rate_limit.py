# services/rate_limit.py
from __future__ import annotations
import time
from dataclasses import dataclass
from threading import Lock

from settings import MESSAGE_RATE_LIMIT, MESSAGE_RATE_WINDOW_SECONDS


@dataclass
class Bucket:
    tokens: float
    last: float


class TokenBucketLimiter:
    """
    In-memory token bucket.
    Not multi-instance safe (fine for demo). Replace with Redis for production.
    """
    def __init__(self, capacity: int, window_seconds: int):
        self.capacity = float(capacity)
        self.refill_rate = float(capacity) / float(window_seconds)  # tokens/sec
        self._buckets: dict[int, Bucket] = {}
        self._lock = Lock()

    def allow(self, user_id: int, cost: float = 1.0) -> tuple[bool, float]:
        """
        Returns (allowed, retry_after_seconds).
        """
        now = time.monotonic()
        with self._lock:
            b = self._buckets.get(user_id)
            if b is None:
                b = Bucket(tokens=self.capacity, last=now)
                self._buckets[user_id] = b

            # refill
            elapsed = now - b.last
            b.tokens = min(self.capacity, b.tokens + elapsed * self.refill_rate)
            b.last = now

            if b.tokens >= cost:
                b.tokens -= cost
                return True, 0.0

            missing = cost - b.tokens
            retry_after = missing / self.refill_rate if self.refill_rate > 0 else 1.0
            return False, retry_after


message_limiter = TokenBucketLimiter(
    capacity=MESSAGE_RATE_LIMIT,
    window_seconds=MESSAGE_RATE_WINDOW_SECONDS,
)