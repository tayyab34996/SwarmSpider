import asyncio
import aiohttp
import logging
import json
from typing import List
from urllib.parse import urljoin

from fetch.fetcher import Fetcher
from parse.extractor import Extractor
from db.database import Database
from schema.models import ProductRecord

logger = logging.getLogger(__name__)

class PipelineMetrics:
    def __init__(self):
        self.requested = 0
        self.fetched = 0
        self.validated = 0
        self.written = 0
        self.failed_fetch = 0
        self.failed_parse = 0
        self.failed_write = 0

class Orchestrator:
    def __init__(self, base_url: str, total_pages: int, db: Database, fetch_concurrency: int = 20, batch_size: int = 10):
        self.base_url = base_url
        self.total_pages = total_pages
        self.db = db
        self.fetcher = Fetcher(concurrency_limit=fetch_concurrency)
        self.extractor = Extractor()
        self.batch_size = batch_size
        
        # Bounded queue applies backpressure. 
        # If the queue has 50 items, producers (fetchers) will block on queue.put(),
        # naturally slowing down fetching until writes catch up.
        self.record_queue = asyncio.Queue(maxsize=50)
        self.metrics = PipelineMetrics()
        
    async def _fetch_and_process(self, session: aiohttp.ClientSession, url: str):
        self.metrics.requested += 1
        html = await self.fetcher.fetch_page(session, url)
        if not html:
            self.metrics.failed_fetch += 1
            return
            
        self.metrics.fetched += 1
        record, err = self.extractor.extract_and_validate(html, url)
        
        if err:
            self.metrics.failed_parse += 1
            logger.warning(f"Failed to parse {url}: {err}")
            with open("rejected_pages.jsonl", "a") as f:
                f.write(json.dumps({"url": url, "error": err}) + "\n")
            return
            
        self.metrics.validated += 1
        
        # This will block if queue is full (Backpressure)
        await self.record_queue.put(record)

    async def _writer_worker(self):
        """Consumes records from the queue and writes to the DB in batches."""
        batch: List[ProductRecord] = []
        while True:
            try:
                # Wait for a record. If we timeout and have a batch, we write it.
                # If we timeout and don't have a batch, we keep waiting.
                record = await asyncio.wait_for(self.record_queue.get(), timeout=1.0)
                if record is None: # Sentinel value to stop
                    self.record_queue.task_done()
                    break
                    
                batch.append(record)
                self.record_queue.task_done()
                
            except asyncio.TimeoutError:
                pass # Time to flush the batch if there's any
                
            if len(batch) >= self.batch_size or (len(batch) > 0 and self.record_queue.empty()):
                try:
                    await self.db.upsert_records(batch)
                    self.metrics.written += len(batch)
                except Exception as e:
                    self.metrics.failed_write += len(batch)
                    logger.error(f"Writer worker failed to write batch: {e}")
                finally:
                    batch.clear()

        # Final flush just in case
        if batch:
            try:
                await self.db.upsert_records(batch)
                self.metrics.written += len(batch)
            except Exception as e:
                self.metrics.failed_write += len(batch)
                logger.error(f"Writer worker failed to write final batch: {e}")

    async def run(self):
        # Create table
        await self.db.init_db()
        
        # Clear out rejects file for new run
        with open("rejected_pages.jsonl", "w") as f:
            f.write("")
        
        writer_task = asyncio.create_task(self._writer_worker())
        
        urls = [urljoin(self.base_url, f"/page/{i}") for i in range(1, self.total_pages + 1)]
        
        async with aiohttp.ClientSession() as session:
            # We use gather to launch all fetch tasks.
            # The concurrency is bounded inside the fetcher via semaphore.
            tasks = [self._fetch_and_process(session, url) for url in urls]
            await asyncio.gather(*tasks)
            
        # Signal the writer to finish
        await self.record_queue.put(None)
        await writer_task
