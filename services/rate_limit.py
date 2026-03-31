"""
In-memory rate limiting utilities.

This module implements a token-bucket rate limiter used to control how often
a user can perform certain actions, such as sending chat messages.

Current usage:
- message_limiter limits how frequently each user can send messages

Design notes:
- state is stored in memory, so this works only within a single app instance
- this is suitable for local development and demo deployments
- for production across multiple instances, Redis or another shared store
  should be used instead
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from settings import MESSAGE_RATE_LIMIT, MESSAGE_RATE_WINDOW_SECONDS


@dataclass
class Bucket:
    """
    Per-user token bucket state.

    Attributes:
        tokens: Current number of available tokens in the bucket.
        last: Last time the bucket was updated, measured with time.monotonic().
    """

    tokens: float
    last: float


class TokenBucketLimiter:
    """
    In-memory token bucket rate limiter.

    The algorithm works like this:
    - each user starts with a full bucket of tokens
    - each action consumes one or more tokens
    - tokens refill gradually over time
    - if enough tokens are available, the action is allowed
    - otherwise, the action is denied and a retry-after delay is returned

    Important:
        This limiter is process-local and not multi-instance safe.
    """

    def __init__(self, capacity: int, window_seconds: int) -> None:
        """
        Initialize the limiter.

        Args:
            capacity: Maximum number of tokens in each bucket.
            window_seconds: Time window over which the bucket fully refills.

        Derived values:
            refill_rate = capacity / window_seconds
            This is the number of tokens added per second.
        """

        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.capacity = float(capacity)
        self.refill_rate = float(capacity) / float(window_seconds)
        self._buckets: dict[int, Bucket] = {}
        self._lock = Lock()

    def allow(self, user_id: int, cost: float = 1.0) -> tuple[bool, float]:
        """
        Attempt to consume tokens for a user's action.

        Flow:
        1. Get the current monotonic time.
        2. Load or create the user's bucket.
        3. Refill the bucket based on elapsed time since last update.
        4. If enough tokens exist, deduct the action cost and allow it.
        5. Otherwise, deny it and calculate how long until enough tokens refill.

        Args:
            user_id: ID of the user performing the action.
            cost: Number of tokens the action should consume.
                Defaults to 1.0.

        Returns:
            Tuple of:
            - allowed: True if the action is permitted, otherwise False
            - retry_after_seconds: 0.0 if allowed, otherwise estimated wait time
              before enough tokens are available

        Notes:
            Uses time.monotonic() rather than time.time() so rate limiting is not
            affected by system clock changes.
        """
        
        now = time.monotonic()

        with self._lock:
            bucket = self._buckets.get(user_id)
            if bucket is None:
                bucket = Bucket(tokens=self.capacity, last=now)
                self._buckets[user_id] = bucket

            # Refill tokens based on elapsed time since the last update.
            elapsed = now - bucket.last
            bucket.tokens = min(
                self.capacity,
                bucket.tokens + elapsed * self.refill_rate,
            )
            bucket.last = now

            # If enough tokens are available, consume them and allow the action.
            if bucket.tokens >= cost:
                bucket.tokens -= cost
                return True, 0.0

            # Otherwise, compute how long until enough tokens are refilled.
            missing = cost - bucket.tokens
            retry_after = missing / self.refill_rate if self.refill_rate > 0 else 1.0
            return False, retry_after


# Shared limiter instance for chat message sending.
message_limiter = TokenBucketLimiter(
    capacity=MESSAGE_RATE_LIMIT,
    window_seconds=MESSAGE_RATE_WINDOW_SECONDS,
)