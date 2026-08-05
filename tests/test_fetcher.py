"""
Unit tests for SwarmSpider – fetch/fetcher.py
Tests cover: successful fetch, retry on 500, fail after max retries, client error no retry.
"""
import sys
import os
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fetch.fetcher import Fetcher


def make_mock_response(status: int, text: str = "<html>ok</html>") -> MagicMock:
    """Helper to build a mock aiohttp response context manager."""
    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=text)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestFetcher:
    @pytest.mark.asyncio
    async def test_successful_fetch(self) -> None:
        fetcher = Fetcher(concurrency_limit=5, max_retries=3, timeout_seconds=5)
        session = MagicMock()
        session.get.return_value = make_mock_response(200, "<html>ok</html>")

        result = await fetcher.fetch_page(session, "http://test/page/1")

        assert result == "<html>ok</html>"
        assert fetcher.metrics.success == 1
        assert fetcher.metrics.failed == 0

    @pytest.mark.asyncio
    async def test_500_increments_metrics_and_fails(self) -> None:
        fetcher = Fetcher(concurrency_limit=5, max_retries=2, timeout_seconds=5)
        session = MagicMock()
        # Always return 500
        session.get.return_value = make_mock_response(500)
        # Patch asyncio.sleep to avoid waiting in tests
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await fetcher.fetch_page(session, "http://test/page/2")

        assert result is None
        assert fetcher.metrics.failed == 1

    @pytest.mark.asyncio
    async def test_404_does_not_retry(self) -> None:
        fetcher = Fetcher(concurrency_limit=5, max_retries=3, timeout_seconds=5)
        session = MagicMock()
        session.get.return_value = make_mock_response(404)

        result = await fetcher.fetch_page(session, "http://test/page/3")

        assert result is None
        # Should only have been called once (no retry for 4xx)
        assert session.get.call_count == 1
        assert fetcher.metrics.failed == 1

    @pytest.mark.asyncio
    async def test_metrics_requested_incremented(self) -> None:
        fetcher = Fetcher(concurrency_limit=5, max_retries=1, timeout_seconds=5)
        session = MagicMock()
        session.get.return_value = make_mock_response(200)

        await fetcher.fetch_page(session, "http://test/page/4")

        assert fetcher.metrics.requested == 1

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Verify the semaphore is initialized with the right limit."""
        fetcher = Fetcher(concurrency_limit=7)
        assert fetcher.semaphore._value == 7
