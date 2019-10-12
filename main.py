import aiohttp
import asyncio
from os import listdir
from os.path import isfile, join
from urllib.parse import urlparse

import adapters
import aiofiles
import pymorphy2
from text_tools import split_by_words, calculate_jaundice_rate


def extract_domain_name(url):
    return '_'.join(urlparse(url).netloc.split('.'))


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


async def main():

    path = 'charged_dict'
    charged_words = await get_charged_words(path)

    morph = pymorphy2.MorphAnalyzer()

    url = 'https://inosmi.ru/science/20191011/246010355.html'

    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url)

        sanitizer_name = extract_domain_name(url)
        sanitizer = adapters.SANITIZERS.get(sanitizer_name)

        if sanitizer:
            text = sanitizer(html, plaintext=True)
            article_words = split_by_words(morph, text)
            rate = calculate_jaundice_rate(article_words, charged_words)
            print(f'Рейтинг: {rate}\nСлов в статье: {len(article_words)}')


if __name__ == '__main__':
    asyncio.run(main())
