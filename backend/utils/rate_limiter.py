import time
import logging
from threading import RLock

from backend.config.settings import REDIS_URL


logger = logging.getLogger(__name__)


class InMemoryRateLimiter:

    def __init__(
        self,
        limit: int,
        window_seconds: int = 60
    ):

        self.limit = limit
        self.window_seconds = window_seconds
        self._requests = {}
        self._lock = RLock()

    def reset(self):

        with self._lock:

            self._requests.clear()

    def allow(
        self,
        key: str
    ):

        now = time.time()
        window_start = (
            now
            - self.window_seconds
        )

        with self._lock:

            timestamps = [
                timestamp
                for timestamp in self._requests.get(
                    key,
                    []
                )
                if timestamp > window_start
            ]

            if len(timestamps) >= self.limit:

                retry_after = int(
                    max(
                        1,
                        self.window_seconds
                        - (
                            now
                            - timestamps[0]
                        )
                    )
                )

                self._requests[key] = timestamps

                return False, retry_after

            timestamps.append(now)
            self._requests[key] = timestamps

            return True, 0


class RedisFixedWindowRateLimiter:

    def __init__(
        self,
        limit: int,
        window_seconds: int = 60,
        namespace: str = "chat",
        client=None
    ):

        self.limit = limit
        self.window_seconds = window_seconds
        self.namespace = namespace
        self.client = client

    def _key(
        self,
        key: str,
        window_id: int
    ):

        return (
            f"finintel:rate_limit:{self.namespace}:"
            f"{key}:{window_id}"
        )

    def reset(self):

        pattern = (
            f"finintel:rate_limit:{self.namespace}:*"
        )

        for key in self.client.scan_iter(
            match=pattern
        ):

            self.client.delete(
                key
            )

    def allow(
        self,
        key: str
    ):

        now = int(
            time.time()
        )
        window_id = (
            now
            // self.window_seconds
        )
        redis_key = self._key(
            key,
            window_id
        )

        count = self.client.incr(
            redis_key
        )

        if count == 1:

            self.client.expire(
                redis_key,
                self.window_seconds
                + 1
            )

        if count > self.limit:

            retry_after = max(
                1,
                (
                    (window_id + 1)
                    * self.window_seconds
                )
                - now
            )

            return False, retry_after

        return True, 0


def build_rate_limiter(
    limit: int,
    window_seconds: int = 60,
    namespace: str = "chat"
):

    if not REDIS_URL:

        return InMemoryRateLimiter(
            limit=limit,
            window_seconds=window_seconds
        )

    try:

        from redis import Redis

        client = Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1,
            decode_responses=True
        )
        client.ping()

        logger.info(
            "redis_rate_limiter_enabled namespace=%s",
            namespace
        )

        return RedisFixedWindowRateLimiter(
            limit=limit,
            window_seconds=window_seconds,
            namespace=namespace,
            client=client
        )

    except Exception:

        logger.exception(
            "redis_rate_limiter_unavailable namespace=%s fallback=in_memory",
            namespace
        )

        return InMemoryRateLimiter(
            limit=limit,
            window_seconds=window_seconds
        )
