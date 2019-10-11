import aiohttp
import asyncio
from urllib.parse import urlparse

import adapters


def extract_domain_name(url):
    return '_'.join(urlparse(url).netloc.split('.'))


async def fetch(session, url):
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.text()


async def main():
    url = 'https://inosmi.ru/science/20191011/246010355.html'
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, url)

        sanitizer_name = extract_domain_name(url)
        sanitizer = adapters.SANITIZERS.get(sanitizer_name)

        if sanitizer:
            print(sanitizer(html, plaintext=True))


if __name__ == '__main__':
    asyncio.run(main())
