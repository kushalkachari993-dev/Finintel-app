import time

import pytest

from backend.utils.async_execution import run_blocking


def blocking_value():
    return "ok"


def slow_blocking_value():
    time.sleep(0.05)
    return "late"


@pytest.mark.anyio
async def test_run_blocking_returns_value():
    assert await run_blocking(
        blocking_value,
        timeout_seconds=1
    ) == "ok"


@pytest.mark.anyio
async def test_run_blocking_raises_timeout():
    with pytest.raises(
        TimeoutError
    ):
        await run_blocking(
            slow_blocking_value,
            timeout_seconds=0.001
        )
