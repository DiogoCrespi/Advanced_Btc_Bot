import time
import asyncio
from unittest.mock import patch
from logic.news_fetcher import NewsFetcher

class MockResponse:
    def __init__(self, json_data, status, text=""):
        self.json_data = json_data
        self.status = status
        self._text = text

    async def json(self):
        return self.json_data

    async def text(self):
        return self._text

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

def mock_get(*args, **kwargs):
    time.sleep(1) # Simulate network delay. In actual async, it would be await asyncio.sleep
    return MockResponse({"status": "ok", "articles": [{"title": "Test"}]}, 200)

async def mock_post(*args, **kwargs):
    await asyncio.sleep(1) # Simulate network delay properly
    return MockResponse({"results": [{"title": "Test"}]}, 200)

class AsyncMockResponse:
    def __init__(self, json_data, status):
        self.json_data = json_data
        self.status = status

    async def json(self):
        return self.json_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

class MockSession:
    def get(self, *args, **kwargs):
        return MockResponse({"status": "ok", "articles": [{"title": "Test"}]}, 200)

    def post(self, *args, **kwargs):
        return MockResponse({"results": [{"title": "Test"}]}, 200)

@patch('aiohttp.ClientSession.get')
@patch('aiohttp.ClientSession.post')
@patch('logic.news_fetcher.NEWSAPI_KEY', 'dummy')
@patch('logic.news_fetcher.TAVILY_KEY', 'dummy')
def benchmark(mock_post, mock_get):

    async def async_mock_get(*args, **kwargs):
        await asyncio.sleep(1)
        return MockResponse({"status": "ok", "articles": [{"title": "Test"}]}, 200)

    async def async_mock_post(*args, **kwargs):
        await asyncio.sleep(1)
        return MockResponse({"results": [{"title": "Test"}]}, 200)

    # Note that patch with MagicMock behaves differently for async context managers
    # We will test the async execution.
    pass

import aiohttp
from unittest.mock import AsyncMock

async def run_benchmark():
    fetcher = NewsFetcher()
    fetcher._newsapi_ok = True
    fetcher._tavily_ok = True
    import logic.news_fetcher
    logic.news_fetcher.NEWSAPI_KEY = "dummy"
    logic.news_fetcher.TAVILY_KEY = "dummy"

    # We patch ClientSession to return our async context managers
    original_session = aiohttp.ClientSession

    class FakeSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        def get(self, *args, **kwargs):
            class Ctx:
                async def __aenter__(self):
                    await asyncio.sleep(1)
                    return MockResponse({"status": "ok", "articles": [{"title": "Test"}]}, 200)
                async def __aexit__(self, exc_type, exc, tb):
                    pass
            return Ctx()

        def post(self, *args, **kwargs):
            class Ctx:
                async def __aenter__(self):
                    await asyncio.sleep(1)
                    return MockResponse({"results": [{"title": "Test"}]}, 200)
                async def __aexit__(self, exc_type, exc, tb):
                    pass
            return Ctx()

    aiohttp.ClientSession = FakeSession

    start = time.time()
    articles = await fetcher.fetch_async()
    end = time.time()
    print(f"Time taken: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
