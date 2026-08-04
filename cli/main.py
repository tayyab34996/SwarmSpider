import asyncio
import argparse
import time
import sys
import os
import logging

# Ensure modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.database import Database
from pipeline.orchestrator import Orchestrator
from reporting.logger import configure_logging, print_summary

async def run_scraper(args):
    db = Database(
        db_path=args.db_url,
        pool_size=args.pool_size,
        write_concurrency=args.write_concurrency
    )
    
    orchestrator = Orchestrator(
        base_url=args.url,
        total_pages=args.count,
        db=db,
        fetch_concurrency=args.fetch_concurrency,
        batch_size=args.batch_size
    )
    
    start_time = time.time()
    await orchestrator.run()
    duration = time.time() - start_time
    
    print_summary(orchestrator.metrics, duration)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmSpider - Asynchronous Web Scraper")
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Base URL of target server")
    parser.add_argument("--count", type=int, default=120, help="Total pages to fetch")
    parser.add_argument("--fetch-concurrency", type=int, default=20, help="Max concurrent fetches")
    parser.add_argument("--write-concurrency", type=int, default=2, help="Max concurrent DB write operations")
    parser.add_argument("--batch-size", type=int, default=10, help="Records per DB write batch")
    parser.add_argument("--pool-size", type=int, default=5, help="Database connection pool size")
    parser.add_argument("--db-url", default="sqlite+aiosqlite:///scraper.db", help="SQLAlchemy Async Database URL")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    configure_logging(level=logging.DEBUG if args.debug else logging.INFO)
    
    # Run the pipeline
    asyncio.run(run_scraper(args))
