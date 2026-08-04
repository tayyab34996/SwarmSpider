import logging

def configure_logging(level=logging.INFO):
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def print_summary(metrics, duration: float):
    print("\n" + "=" * 40)
    print("SwarmSpider Run Summary")
    print("=" * 40)
    print(f"Total Pages Requested:       {metrics.requested}")
    print(f"Successfully Fetched:        {metrics.fetched}")
    print(f"Failed to Fetch:             {metrics.failed_fetch}")
    print("-" * 40)
    print(f"Successfully Validated:      {metrics.validated}")
    print(f"Failed to Parse/Validate:    {metrics.failed_parse}")
    print("-" * 40)
    print(f"Successfully Written to DB:  {metrics.written}")
    print(f"Failed to Write to DB:       {metrics.failed_write}")
    print("=" * 40)
    print(f"Total Wall-Clock Time:       {duration:.2f} seconds")
    
    throughput = metrics.written / duration if duration > 0 else 0.0
    print(f"Effective Throughput:        {throughput:.2f} items written/sec")
    print("=" * 40 + "\n")
