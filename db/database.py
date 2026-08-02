import asyncio
import logging
import time
from typing import List

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, Float, Boolean
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.pool import QueuePool

from schema.models import ProductRecord

logger = logging.getLogger(__name__)

Base = declarative_base()

class ProductModel(Base):
    __tablename__ = 'products'
    url = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    in_stock = Column(Boolean, nullable=False)
    description = Column(String, nullable=True)

class Database:
    def __init__(self, db_path: str = "sqlite+aiosqlite:///scraper.db", pool_size: int = 5, write_concurrency: int = 2):
        # We configure a connection pool to bound database connections.
        # Even with SQLite, a connection pool ensures we don't open hundreds of connections
        # simultaneously and exhaust file descriptors.
        self.engine = create_async_engine(
            db_path,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=2,
            connect_args={"timeout": 15.0} # Increase timeout for SQLite lock contention
        )
        self.async_session_maker = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        
        # Throttles concurrent writes independently of fetches.
        # If 100 fetches finish at once, only `write_concurrency` (e.g. 2) will attempt
        # to open a write transaction simultaneously.
        self.write_semaphore = asyncio.Semaphore(write_concurrency)
        self.max_retries = 5

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def upsert_records(self, records: List[ProductRecord]):
        """
        Idempotent write: UPSERT based on 'url'.
        Uses batched writes for efficiency.
        """
        if not records:
            return

        values = [
            {
                "url": r.url,
                "title": r.title,
                "price": r.price,
                "in_stock": r.in_stock,
                "description": r.description
            }
            for r in records
        ]

        # SQLite UPSERT logic
        stmt = insert(ProductModel).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=['url'],
            set_={
                'title': stmt.excluded.title,
                'price': stmt.excluded.price,
                'in_stock': stmt.excluded.in_stock,
                'description': stmt.excluded.description
            }
        )

        wait_start = time.time()
        
        # Apply write-side throttling/backpressure
        async with self.write_semaphore:
            wait_duration = time.time() - wait_start
            if wait_duration > 0.5:
                logger.warning(f"Write pool saturated. Waited {wait_duration:.2f}s for DB write semaphore.")

            for attempt in range(1, self.max_retries + 1):
                try:
                    async with self.async_session_maker() as session:
                        async with session.begin():
                            await session.execute(stmt)
                            return
                except Exception as e:
                    err_str = str(e).lower()
                    if "locked" in err_str or "operationalerror" in err_str:
                        logger.warning(f"Database lock contention (attempt {attempt}/{self.max_retries}): {e}")
                    else:
                        logger.error(f"Database write error: {e}")
                        raise
                        
                    if attempt < self.max_retries:
                        backoff = 0.5 * (2 ** attempt)
                        logger.info(f"Retrying batched write of {len(records)} records in {backoff}s...")
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(f"Failed to write batch after {self.max_retries} attempts.")
                        raise
