"""
Unit tests for SwarmSpider – db/database.py
Tests cover: DB initialization, upsert idempotency, empty batch is a no-op.
"""
import sys
import os
import asyncio
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import Database
from schema.models import ProductRecord


def make_records(n: int = 3) -> list[ProductRecord]:
    return [
        ProductRecord(
            url=f"http://test/page/{i}",
            title=f"Product {i}",
            price=float(i) * 1.5,
            in_stock=(i % 2 == 0),
        )
        for i in range(1, n + 1)
    ]


class TestDatabase:
    @pytest.mark.asyncio
    async def test_init_db_creates_table(self) -> None:
        db = Database(db_path="sqlite+aiosqlite:///:memory:", pool_size=2, write_concurrency=1)
        # Should not raise
        await db.init_db()

    @pytest.mark.asyncio
    async def test_upsert_empty_batch_is_noop(self) -> None:
        db = Database(db_path="sqlite+aiosqlite:///:memory:", pool_size=2, write_concurrency=1)
        await db.init_db()
        # Should not raise and should be a no-op
        await db.upsert_records([])

    @pytest.mark.asyncio
    async def test_upsert_inserts_records(self) -> None:
        db = Database(db_path="sqlite+aiosqlite:///:memory:", pool_size=2, write_concurrency=1)
        await db.init_db()
        records = make_records(3)
        await db.upsert_records(records)

        # Verify by re-querying
        from sqlalchemy import text
        async with db.async_session_maker() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM products"))
            count = result.scalar()
        assert count == 3

    @pytest.mark.asyncio
    async def test_upsert_is_idempotent(self) -> None:
        """Writing the same records twice must not create duplicates."""
        db = Database(db_path="sqlite+aiosqlite:///:memory:", pool_size=2, write_concurrency=1)
        await db.init_db()
        records = make_records(5)

        await db.upsert_records(records)
        await db.upsert_records(records)  # duplicate write

        from sqlalchemy import text
        async with db.async_session_maker() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM products"))
            count = result.scalar()
        assert count == 5  # still 5, no duplicates

    @pytest.mark.asyncio
    async def test_upsert_updates_existing_record(self) -> None:
        """An upsert for the same URL must update the existing row."""
        db = Database(db_path="sqlite+aiosqlite:///:memory:", pool_size=2, write_concurrency=1)
        await db.init_db()

        original = [ProductRecord(url="http://test/page/1", title="Old Title", price=1.0, in_stock=True)]
        updated = [ProductRecord(url="http://test/page/1", title="New Title", price=9.99, in_stock=False)]

        await db.upsert_records(original)
        await db.upsert_records(updated)

        from sqlalchemy import text
        async with db.async_session_maker() as session:
            result = await session.execute(text("SELECT title, price FROM products WHERE url='http://test/page/1'"))
            row = result.fetchone()

        assert row[0] == "New Title"
        assert row[1] == 9.99
