import time

from backend.tools.ticker_resolver import TickerResolver
from backend.utils.rate_limiter import RedisFixedWindowRateLimiter
from backend.utils.simple_cache import RedisTTLCache
from backend.utils.simple_cache import TTLCache


class FakeRedis:

    def __init__(self):

        self.items = {}
        self.expiry = {}

    def get(
        self,
        key
    ):

        expires_at = self.expiry.get(key)

        if expires_at is not None and expires_at <= time.time():

            self.items.pop(
                key,
                None
            )
            self.expiry.pop(
                key,
                None
            )

            return None

        return self.items.get(key)

    def setex(
        self,
        key,
        ttl,
        value
    ):

        self.items[key] = value
        self.expiry[key] = (
            time.time()
            + ttl
        )

    def incr(
        self,
        key
    ):

        self.items[key] = int(
            self.items.get(
                key,
                0
            )
        ) + 1

        return self.items[key]

    def expire(
        self,
        key,
        ttl
    ):

        self.expiry[key] = (
            time.time()
            + ttl
        )

    def scan_iter(
        self,
        match
    ):

        prefix = match.rstrip("*")
        return [
            key
            for key in self.items
            if key.startswith(prefix)
        ]

    def delete(
        self,
        key
    ):

        self.items.pop(
            key,
            None
        )
        self.expiry.pop(
            key,
            None
        )


def test_ttl_cache_expires_items():

    cache = TTLCache(
        ttl_seconds=0
    )

    cache.set(
        "key",
        "value"
    )

    time.sleep(0.01)

    assert cache.get("key") is None


def test_redis_ttl_cache_uses_shared_client():

    client = FakeRedis()
    first = RedisTTLCache(
        ttl_seconds=60,
        namespace="test",
        client=client
    )
    second = RedisTTLCache(
        ttl_seconds=60,
        namespace="test",
        client=client
    )

    first.set(
        "key",
        {
            "value": 1
        }
    )

    assert second.get("key") == {
        "value": 1
    }


def test_redis_rate_limiter_shares_counts_across_instances():

    client = FakeRedis()
    first = RedisFixedWindowRateLimiter(
        limit=1,
        window_seconds=60,
        namespace="test",
        client=client
    )
    second = RedisFixedWindowRateLimiter(
        limit=1,
        window_seconds=60,
        namespace="test",
        client=client
    )

    assert first.allow("api-key") == (True, 0)

    allowed, retry_after = second.allow("api-key")

    assert allowed is False
    assert retry_after > 0


def test_ticker_resolver_uses_local_ticker_map():

    resolver = TickerResolver()

    result = resolver.resolve(
        "Current price of HDFC Bank"
    )

    assert result["ticker"] == "HDFCBANK.NS"
    assert result["confidence"] == 0.97


def test_ticker_resolver_uses_symbol_master_for_wider_coverage():

    resolver = TickerResolver()

    result = resolver.resolve(
        "Current price of Asian Paints"
    )

    assert result["ticker"] == "ASIANPAINT.NS"
    assert result["company_name"] == "Asian Paints"
