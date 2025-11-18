"""Rate limiting utilities for API requests."""

import time
import threading
from collections import defaultdict
from typing import Callable, Optional, Union

from .config import get_config


class NoOpRateLimiter:
    """
    No-op rate limiter for development use when rate limiting is disabled.

    This class provides the same interface as RateLimiter but performs no
    rate limiting operations. Use only in development environments.
    """

    def acquire(self, key: str = "default") -> None:
        """
        No-op acquire method. Does nothing.

        Args:
            key: Optional key (ignored)
        """
        pass

    def __call__(self, func: Callable) -> Callable:
        """
        Return a decorator that does not rate limit (no-op).

        Args:
            func: Function to wrap (returned unchanged)

        Returns:
            Original function unchanged
        """
        return func


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.

    Limits the number of operations per time window.
    """

    def __init__(self, max_calls: int, time_window: float):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed in the time window
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: defaultdict[str, list] = defaultdict(list)
        self.lock = threading.Lock()

    def _clean_old_calls(self, key: str, current_time: float) -> None:
        """Remove calls outside the current time window."""
        cutoff_time = current_time - self.time_window
        self.calls[key] = [
            call_time for call_time in self.calls[key] if call_time > cutoff_time
        ]

    def acquire(self, key: str = "default") -> None:
        """
        Acquire permission to make a call. Blocks if rate limit is exceeded.

        Args:
            key: Optional key to track different rate limit groups

        Raises:
            RuntimeError: If rate limit is exceeded (should not happen in normal operation)
        """
        with self.lock:
            current_time = time.time()
            self._clean_old_calls(key, current_time)

            if len(self.calls[key]) >= self.max_calls:
                # Calculate wait time until oldest call expires
                oldest_call = min(self.calls[key])
                wait_time = self.time_window - (current_time - oldest_call)
                if wait_time > 0:
                    time.sleep(wait_time)
                    current_time = time.time()
                    self._clean_old_calls(key, current_time)

            # Record this call
            self.calls[key].append(current_time)

    def __call__(self, func: Callable) -> Callable:
        """
        Return a decorator to rate limit a function.

        Args:
            func: Function to rate limit

        Returns:
            Wrapped function with rate limiting
        """

        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)

        return wrapper


# Global rate limiters for different operations
# These are initialized lazily to allow config to be loaded first
_db_rate_limiter: Optional[Union[RateLimiter, NoOpRateLimiter]] = None
_embedding_rate_limiter: Optional[Union[RateLimiter, NoOpRateLimiter]] = None


def _get_db_rate_limiter() -> Union[RateLimiter, NoOpRateLimiter]:
    """Get or create the database rate limiter with config values."""
    global _db_rate_limiter
    if _db_rate_limiter is None:
        config = get_config()
        if config.rate_limiting_disabled:
            _db_rate_limiter = NoOpRateLimiter()
        else:
            _db_rate_limiter = RateLimiter(
                max_calls=config.db_rate_limit, time_window=1.0
            )
    return _db_rate_limiter


def _get_embedding_rate_limiter() -> Union[RateLimiter, NoOpRateLimiter]:
    """Get or create the embedding rate limiter with config values."""
    global _embedding_rate_limiter
    if _embedding_rate_limiter is None:
        config = get_config()
        if config.rate_limiting_disabled:
            _embedding_rate_limiter = NoOpRateLimiter()
        else:
            _embedding_rate_limiter = RateLimiter(
                max_calls=config.embedding_rate_limit, time_window=1.0
            )
    return _embedding_rate_limiter


# Module-level access using __getattr__ for lazy initialization
# This allows importing like: from ...rate_limiter import db_rate_limiter
def __getattr__(name: str):
    """Module-level attribute access for rate limiters (lazy initialization)."""
    if name == "db_rate_limiter":
        return _get_db_rate_limiter()
    if name == "embedding_rate_limiter":
        return _get_embedding_rate_limiter()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
