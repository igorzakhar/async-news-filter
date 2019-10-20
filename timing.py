import asyncio
import contextlib
import time

from text_tools import split_by_words


@contextlib.asynccontextmanager
async def measure_exec_time(morph, text):
    start_time = time.monotonic()
    article_words = split_by_words(morph, text)
    end_time = time.monotonic() - start_time
    yield end_time, article_words
