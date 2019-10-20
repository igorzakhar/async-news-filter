import aiohttp
import asyncio
import contextlib
from enum import Enum
import logging
from os import listdir
from os.path import isfile, join
from urllib.parse import urlparse

import aiofiles
import aionursery
from async_timeout import timeout
import pymorphy2

import adapters
from text_tools import split_by_words, calculate_jaundice_rate
from timing import measure_exec_time


logging.getLogger('asyncio').setLevel(logging.WARNING)
logging.getLogger('pymorphy2').setLevel(logging.WARNING)


TEST_ARTICLES = [
    'https://url_does_not_exist.ru',
    'https://lenta.ru/news/2019/10/15/real/',
    'https://inosmi.ru/social/20191004/245951541.html',
    'https://inosmi.ru/social/20191008/245982282.html',
    'https://inosmi.ru/science/20191006/245965114.html',
    'https://inosmi.ru/science/20191009/245994605.html',
    'https://inosmi.ru/science/20191011/246010355.html',
    'https://dvmn.org/media/filer_public/51/83/51830f54-7ec7-4702-847b-c5790ed3724c/gogol_nikolay_taras_bulba_-_bookscafenet.txt'
]


class ProcessingStatus(Enum):
    OK = 'OK'
    FETCH_ERROR = 'FETCH_ERROR'
    PARSING_ERROR = 'PARSING_ERROR'
    TIMEOUT = 'TIMEOUT'


def get_sanitizer(url):
    domain_name = urlparse(url).netloc
    sanitizer_name = '_'.join(domain_name.split('.'))
    sanitizer = adapters.SANITIZERS.get(sanitizer_name)

    if sanitizer:
        return sanitizer

    raise adapters.ArticleNotFound(f'Статья на {domain_name}')


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


async def process_article(session, morph, charged_words, url, resp_timeout=5):
    result = {
        'title': None,
        'status': None,
        'score': None,
        'words_count': None,
        'exec_time': None
    }

    try:
        async with timeout(resp_timeout):
            article_html = await fetch(session, url)
            adapter = get_sanitizer(url)
    except aiohttp.ClientConnectionError:
        result.update({
            'title': 'URL does not exist',
            'status': ProcessingStatus.FETCH_ERROR.value
        })

    except adapters.ArticleNotFound as err:
        result.update({
            'title': err,
            'status': ProcessingStatus.PARSING_ERROR.value
        })

    except asyncio.TimeoutError:
        result.update({
            'title': 'Timeout Error',
            'status': ProcessingStatus.TIMEOUT.value
        })

    else:
        text, title = adapter(article_html, plaintext=True)
        async with measure_exec_time(morph, text) as (exec_time, words):
            score = calculate_jaundice_rate(words, charged_words)
            result.update({
                'title': title,
                'status': ProcessingStatus.OK.value,
                'score': score,
                'words_count': len(words),
                'exec_time': exec_time
            })
            logging.info(f'Анализ закончен за {exec_time:.2f} сек.')

    return result


async def main():
    logging.basicConfig(level=logging.INFO)
    path = 'charged_dict'
    charged_words = await get_charged_words(path)

    morph = pymorphy2.MorphAnalyzer()

    response_timeout = 10
    tasks = []

    async with aiohttp.ClientSession() as session:
        async with create_handy_nursery() as nursery:
            for url in TEST_ARTICLES:
                task = nursery.start_soon(
                    process_article(
                        session,
                        morph,
                        charged_words,
                        url,
                        resp_timeout=response_timeout
                    )
                )
                tasks.append(task)

    done, _ = await asyncio.wait(tasks)

    for task in done:
        print('Заголовок:', task.result()['title'])
        print('Статус:', task.result()['status'])
        print('Рейтинг:', task.result()['score'])
        print('Слов в статье:', task.result()['words_count'])
        print()


if __name__ == '__main__':
    asyncio.run(main())
