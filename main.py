import aiohttp
import asyncio
import contextlib
from os import listdir
from os.path import isfile, join
from urllib.parse import urlparse

import adapters
import aiofiles
import aionursery
import pymorphy2
from text_tools import split_by_words, calculate_jaundice_rate


TEST_ARTICLES = [
    'https://inosmi.ru/social/20191004/245951541.html',
    'https://inosmi.ru/social/20191008/245982282.html',
    'https://inosmi.ru/science/20191006/245965114.html',
    'https://inosmi.ru/science/20191009/245994605.html',
    'https://inosmi.ru/science/20191011/246010355.html'
]


def extract_domain_name(url):
    return '_'.join(urlparse(url).netloc.split('.'))


@contextlib.asynccontextmanager
async def create_handy_nursery():
    try:
        async with aionursery.Nursery() as nursery:
            yield nursery
    except aionursery.MultiError as e:
        if len(e.exceptions) == 1:
            raise e.exceptions[0]
        raise


async def get_charged_words(path):
    words = []
    files = [join(path, fn) for fn in listdir(path) if isfile(join(path, fn))]
    for file in files:
        async with aiofiles.open(file, mode='r') as afp:
            contents = await afp.read()
            words.extend(contents.strip().split('\n'))
    return words


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, morph, charged_words, url):

    article_html = await fetch(session, url)

    sanitizer_name = extract_domain_name(url)
    sanitizer = adapters.SANITIZERS.get(sanitizer_name)

    if sanitizer:
        text, title = sanitizer(article_html, plaintext=True)
        article_words = split_by_words(morph, text)
        score = calculate_jaundice_rate(article_words, charged_words)
        words_count = len(article_words)

    return title, score, words_count


async def main():
    path = 'charged_dict'
    charged_words = await get_charged_words(path)

    morph = pymorphy2.MorphAnalyzer()

    tasks = []

    async with aiohttp.ClientSession() as session:
        async with create_handy_nursery() as nursery:
            for url in TEST_ARTICLES:
                task = nursery.start_soon(
                    process_article(session, morph, charged_words, url)
                )
                tasks.append(task)

    done, _ = await asyncio.wait(tasks)

    for task in done:
        print('Рейтинг:', task.result()[0])
        print('Слов в статье:', task.result()[2])
        print('Заголовок:', task.result()[1])
        print()


if __name__ == '__main__':
    asyncio.run(main())
