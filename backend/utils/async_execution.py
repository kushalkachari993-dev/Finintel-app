from functools import partial

import anyio


async def run_blocking(
    func,
    *args,
    timeout_seconds: float | None = None,
    **kwargs
):
    call = partial(
        func,
        *args,
        **kwargs
    )

    if timeout_seconds is None:
        return await anyio.to_thread.run_sync(
            call
        )

    with anyio.fail_after(timeout_seconds):
        return await anyio.to_thread.run_sync(
            call,
            abandon_on_cancel=True
        )
