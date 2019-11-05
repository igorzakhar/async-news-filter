import aiohttp
import asyncio
import contextlib
from enum import Enum
import functools
import logging
from os import listdir
from os.path import isfile, join
from urllib.parse import urlparse

from aiohttp import web
import aionursery
from async_timeout import timeout
import pymorphy2

import adapters
from text_tools import calculate_jaundice_rate
from time_measurement import measure_exec_time


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


def get_charged_words(path):
    words = []
    files = [join(path, fn) for fn in listdir(path) if isfile(join(path, fn))]
    for file in files:
        with open(file, mode='r') as fp:
            contents = fp.read()
            words.extend(contents.strip().split('\n'))
    return words


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def process_article(session, morph, charged_words, url, resp_timeout=5):
    article_info = {
        'url': url,
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
        article_info.update({
            'title': 'URL does not exist',
            'status': ProcessingStatus.FETCH_ERROR.value
        })

    except adapters.ArticleNotFound as err:
        article_info.update({
            'title': str(err),
            'status': ProcessingStatus.PARSING_ERROR.value
        })

    except asyncio.TimeoutError:
        article_info.update({
            'title': 'Timeout Error',
            'status': ProcessingStatus.TIMEOUT.value
        })

    else:
        text, title = adapter(article_html, plaintext=True)
        async with measure_exec_time(morph, text) as (exec_time, words, err):
            if err:
                article_info.update({
                    'title': title,
                    'status': ProcessingStatus.TIMEOUT.value,
                })
            else:
                score = calculate_jaundice_rate(words, charged_words)
                article_info.update({
                    'title': title,
                    'status': ProcessingStatus.OK.value,
                    'score': score,
                    'words_count': len(words),
                })
            article_info.update({'exec_time': exec_time})

    return article_info


async def get_articles_analysis_results(morph, charged_words, urls):
    tasks = []

    async with aiohttp.ClientSession() as session:
        async with create_handy_nursery() as nursery:
            for url in urls:
                task = nursery.start_soon(
                    process_article(
                        session,
                        morph,
                        charged_words,
                        url,
                    )
                )
                tasks.append(task)

    done, _ = await asyncio.wait(tasks)

    return [task.result() for task in done]


def prepare_response(data):
    response_fields = ('status', 'url', 'score', 'words_count')
    response = [
        {
            key: value for key, value in entry.items()
            if key in response_fields
        }
        for entry in data
    ]
    return response


async def request_handler(morph, charged_words, request):
    urls = request.query.get('urls')

    if not urls:
        return web.json_response({"error": "bad request"}, status=400)

    urls_list = urls.split(',')
    results = await get_articles_analysis_results(
        morph,
        charged_words,
        urls_list
    )
    response_data = prepare_response(results)

    return web.json_response(response_data)


def main():
    logging.basicConfig(level=logging.INFO)
    path = 'charged_dict'
    charged_words = get_charged_words(path)

    morph = pymorphy2.MorphAnalyzer()

    app = web.Application()
    app.add_routes([
        web.get('/', functools.partial(request_handler, morph, charged_words))
    ])

    web.run_app(app)

if __name__ == '__main__':
    main()
