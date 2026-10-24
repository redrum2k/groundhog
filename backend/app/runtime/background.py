"""Independent bounded lanes; graceful shutdown drains calls before releasing ownership."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def background_workers(operations, *, on_stop=None):
    """Run (name, synchronous attempt, polling interval) lanes in separate thread slots.

    Cancellation of an asyncio wrapper cannot stop synchronous SDK/PDF work. Stop
    selecting new work, then join every active attempt while the caller still owns
    the database worker lock. A hard process exit instead leaves durable leases.
    """
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(
        max_workers=len(operations), thread_name_prefix="catalog-runtime"
    ) as pool:

        async def consume(name, operation, interval):
            while not stop.is_set():
                try:
                    await loop.run_in_executor(pool, operation)
                except Exception as exc:
                    logger.warning(
                        "runtime lane=%s outcome=failed error_type=%s", name, type(exc).__name__
                    )
                try:
                    await asyncio.wait_for(stop.wait(), timeout=interval)
                except TimeoutError:
                    pass

        tasks = [asyncio.create_task(consume(*operation)) for operation in operations]
        try:
            yield
        finally:
            stop.set()
            if on_stop is not None:
                on_stop()
            drained = asyncio.gather(*tasks)
            try:
                await asyncio.shield(drained)
            except asyncio.CancelledError:
                await asyncio.shield(drained)
                raise
