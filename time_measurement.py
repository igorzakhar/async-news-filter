import asyncio
import contextlib
import time

from async_timeout import timeout

from text_tools import split_by_words


@contextlib.asynccontextmanager
async def measure_exec_time(morph, text, to=3):
    start_time = time.monotonic()
    article_words = None
    error = None
    try:
        async with timeout(to):
            article_words = await split_by_words(morph, text)
    except asyncio.TimeoutError as err:
        error = err
    finally:
        end_time = time.monotonic() - start_time
        yield end_time, article_words, error
