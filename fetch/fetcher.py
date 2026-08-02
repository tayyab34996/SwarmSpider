import asyncio
import aiohttp
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class FetchMetrics:
    def __init__(self):
        self.requested = 0
        self.success = 0
        self.failed = 0
        self.retries = 0

class Fetcher:
    def __init__(self, concurrency_limit: int = 20, max_retries: int = 3, timeout_seconds: int = 5):
        # We bound the fetch concurrency with a semaphore. 
        # Reason: A limit of 20 allows substantial concurrency (20 in-flight requests)
        # without exhausting local socket descriptors or triggering anti-DDoS limits on a real target.
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.max_retries = max_retries
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.metrics = FetchMetrics()
        
    async def fetch_page(self, session: aiohttp.ClientSession, url: str) -> Optional[str]:
        self.metrics.requested += 1
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Apply backpressure/bound concurrency here
                async with self.semaphore:
                    logger.debug(f"Fetching {url} (Attempt {attempt}/{self.max_retries})")
                    async with session.get(url, timeout=self.timeout) as response:
                        if response.status == 200:
                            html = await response.text()
                            self.metrics.success += 1
                            return html
                        elif response.status >= 500:
                            logger.warning(f"Transient error {response.status} for {url} (attempt {attempt})")
                        else:
                            logger.error(f"Client error {response.status} for {url}. Not retrying.")
                            self.metrics.failed += 1
                            return None
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.warning(f"Network/Timeout error for {url} (attempt {attempt}): {e}")
                
            if attempt < self.max_retries:
                self.metrics.retries += 1
                backoff = 2 ** attempt
                logger.debug(f"Backing off for {backoff} seconds before retrying {url}...")
                await asyncio.sleep(backoff)
                
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts.")
        self.metrics.failed += 1
        return None
