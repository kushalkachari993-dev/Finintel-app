import time
import logging
import pickle
from threading import RLock

from backend.config.settings import REDIS_URL


logger = logging.getLogger(__name__)


class TTLCache:

    def __init__(
        self,
        ttl_seconds: int
    ):

        self.ttl_seconds = ttl_seconds
        self._items = {}
        self._lock = RLock()

    def get(
        self,
        key
    ):

        now = time.time()

        with self._lock:

            item = self._items.get(key)

            if not item:

                return None

            expires_at, value = item

            if expires_at <= now:

                self._items.pop(
                    key,
                    None
                )

                return None

            return value

    def set(
        self,
        key,
        value
    ):

        expires_at = (
            time.time()
            + self.ttl_seconds
        )

        with self._lock:

            self._items[key] = (
                expires_at,
                value
            )

        return value


class RedisTTLCache:

    def __init__(
        self,
        ttl_seconds: int,
        namespace: str,
        client
    ):

        self.ttl_seconds = ttl_seconds
        self.namespace = namespace
        self.client = client

    def _key(
        self,
        key
    ):

        payload = pickle.dumps(
            key,
            protocol=pickle.HIGHEST_PROTOCOL
        ).hex()

        return f"finintel:cache:{self.namespace}:{payload}"

    def get(
        self,
        key
    ):

        value = self.client.get(
            self._key(key)
        )

        if value is None:

            return None

        return pickle.loads(value)

    def set(
        self,
        key,
        value
    ):

        self.client.setex(
            self._key(key),
            self.ttl_seconds,
            pickle.dumps(
                value,
                protocol=pickle.HIGHEST_PROTOCOL
            )
        )

        return value


def build_cache(
    ttl_seconds: int,
    namespace: str
):

    if not REDIS_URL:

        return TTLCache(
            ttl_seconds=ttl_seconds
        )

    try:

        from redis import Redis

        client = Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=1,
            socket_timeout=1
        )
        client.ping()

        logger.info(
            "redis_cache_enabled namespace=%s",
            namespace
        )

        return RedisTTLCache(
            ttl_seconds=ttl_seconds,
            namespace=namespace,
            client=client
        )

    except Exception:

        logger.exception(
            "redis_cache_unavailable namespace=%s fallback=in_memory",
            namespace
        )

        return TTLCache(
            ttl_seconds=ttl_seconds
        )
