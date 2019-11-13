import asyncio
from urllib.parse import urlparse

import aiohttp
import asynctest
import pytest
import pymorphy2

from main import (
    process_article,
    get_sanitizer,
    get_charged_words,
    ProcessingStatus
)
from adapters import ArticleNotFound


@pytest.fixture()
def charged_words():
    charged_dict_path = 'charged_dict'
    return get_charged_words(charged_dict_path)


@pytest.fixture()
def morph():
    return pymorphy2.MorphAnalyzer()


@pytest.fixture()
def session_mock():
    return asynctest.CoroutineMock()


@pytest.fixture()
def url_nonexistent_adapter():
    return 'https://example.ru'


@pytest.fixture
async def fetch_mock(*args):
    coro_mock = asynctest.CoroutineMock()
    coro_mock.return_value = """
        <h1 class="article-header__title">Test article title</h1>
        <article class="article">Some kind of text.</article>
    """
    return coro_mock


async def mock_client_error(*args):
    raise aiohttp.ClientError


async def mock_fetch_delay(*args):
    delay = 6
    await asyncio.sleep(delay)


def test_article_not_found_raises(url_nonexistent_adapter):
    """test that exception is raised for nonexistent adapters"""
    with pytest.raises(ArticleNotFound):
        get_sanitizer(url_nonexistent_adapter)


@pytest.mark.asyncio
async def test_nonexistent_adapter(
        fetch_mock, url_nonexistent_adapter, charged_words, morph, session_mock
):
    url = url_nonexistent_adapter
    domain_name = urlparse(url).netloc

    expected_data = {
        'url': url,
        'title': f'Статья на {domain_name}',
        'status': ProcessingStatus.PARSING_ERROR.value,
        'score': None,
        'words_count': None,
        'exec_time': None

    }

    with asynctest.patch('main.fetch', side_effect=fetch_mock):
        result = await process_article(session_mock, morph, charged_words, url)
        assert result == expected_data


@pytest.mark.asyncio
async def test_fetch_client_error(session_mock, morph, charged_words):
    url = 'https://url_does_not_exist.ru'

    expected_data = {
        'url': url,
        'title': 'URL does not exist',
        'status': ProcessingStatus.FETCH_ERROR.value,
        'score': None,
        'words_count': None,
        'exec_time': None

    }

    with asynctest.patch('main.fetch', side_effect=mock_client_error):
        result = await process_article(session_mock, morph, charged_words, url)
        assert result == expected_data


@pytest.mark.asyncio
async def test_fetch_timeout_error(session_mock, morph, charged_words):
    url = 'https://inosmi.ru/'

    expected_data = {
        'url': url,
        'title': 'Timeout Error',
        'status': ProcessingStatus.TIMEOUT.value,
        'score': None,
        'words_count': None,
        'exec_time': None

    }

    with asynctest.patch('main.fetch', side_effect=mock_fetch_delay):
        result = await process_article(session_mock, morph, charged_words, url)
        assert result == expected_data


@pytest.mark.asyncio
async def test_success_process_article(
        fetch_mock, session_mock, morph, charged_words):
    url = 'https://inosmi.ru'
    with asynctest.patch('main.fetch', side_effect=fetch_mock):
        result = await process_article(session_mock, morph, charged_words, url)
        assert result['url'] == 'https://inosmi.ru'
        assert result['title'] == 'Test article title'
        assert result['status'] == ProcessingStatus.OK.value
        assert result['words_count'] == 3
