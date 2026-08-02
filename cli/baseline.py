import asyncio
import aiohttp
import time
import argparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import sys
import os

# Add parent dir to path to import schema
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from schema.models import ProductRecord
from pydantic import ValidationError

async def fetch_sequential(base_url, total_pages):
    print(f"Starting sequential fetch of {total_pages} pages...")
    start_time = time.time()
    
    success_count = 0
    fail_count = 0
    reject_count = 0
    records = []
    
    async with aiohttp.ClientSession() as session:
        for i in range(1, total_pages + 1):
            url = urljoin(base_url, f"/page/{i}")
            try:
                # Sequential fetch, waiting for each to complete
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # Parse
                        soup = BeautifulSoup(html, 'html.parser')
                        title_el = soup.find(id='title')
                        price_el = soup.find(id='price')
                        stock_el = soup.find(id='stock')
                        desc_el = soup.find(id='description')
                        
                        if title_el and price_el and stock_el:
                            title = title_el.text
                            price_str = price_el.text.replace('$', '')
                            in_stock = stock_el.text.strip().lower() == "in stock"
                            desc = desc_el.text if desc_el else None
                            
                            try:
                                # Validate
                                record = ProductRecord(
                                    url=url,
                                    title=title,
                                    price=float(price_str),
                                    in_stock=in_stock,
                                    description=desc
                                )
                                records.append(record)
                                success_count += 1
                            except ValidationError as ve:
                                print(f"Validation failed for {url}: {ve}")
                                reject_count += 1
                        else:
                            print(f"Extraction failed for {url}")
                            reject_count += 1
                    else:
                        print(f"Failed to fetch {url}, status: {response.status}")
                        fail_count += 1
            except Exception as e:
                print(f"Error fetching {url}: {e}")
                fail_count += 1
                
    end_time = time.time()
    duration = end_time - start_time
    print("-" * 30)
    print("Sequential Run Summary")
    print(f"Total Pages Requested: {total_pages}")
    print(f"Successfully Fetched & Validated: {success_count}")
    print(f"Failed to Fetch: {fail_count}")
    print(f"Rejected (Validation/Parse Error): {reject_count}")
    print(f"Time Taken: {duration:.2f} seconds")
    print(f"Effective Throughput: {success_count / duration:.2f} pages/sec")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8080", help="Base URL of mock server")
    parser.add_argument("--count", type=int, default=120, help="Number of pages to fetch")
    args = parser.parse_args()
    
    asyncio.run(fetch_sequential(args.url, args.count))
