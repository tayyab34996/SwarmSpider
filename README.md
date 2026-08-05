# SwarmSpider 🕷️

A high-speed **asynchronous web scraper** that fetches 120+ mock pages concurrently, extracts structured records, validates them against a Pydantic schema, and persists results to a SQLite database — demonstrating real-world concurrency control, connection-pooled writes, backpressure, and graceful failure isolation.

---

## Table of Contents
- [Setup & Installation](#setup--installation)
- [Running the Pipeline](#running-the-pipeline)
- [Running Tests](#running-tests)
- [Architecture & Design Decisions](#architecture--design-decisions)
- [Scraped Record Schema](#scraped-record-schema)
- [Performance Comparison](#performance-comparison)
- [Database Stress Test](#database-stress-test)
- [CLI Options Reference](#cli-options-reference)

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- Git

### Step-by-step

```bash
# 1. Clone the repo
git clone https://github.com/tayyab34996/SwarmSpider.git
cd SwarmSpider

# 2. Create and activate a virtual environment
python -m venv .venv

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Running the Pipeline

### Step 1 — Start the mock HTTP server (in one terminal)
```bash
python mock_server.py
```
This starts a local `aiohttp` web server on `http://127.0.0.1:8080` serving 120 product pages.
Some pages intentionally return HTTP 500 or slow responses to exercise retry/backoff logic.

### Step 2 — Run the concurrent scraper (in a second terminal)
```bash
python cli/main.py --count 120
```

### Step 3 (optional) — Run the naive sequential baseline for comparison
```bash
python cli/baseline.py --count 120
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

**23 tests** across 4 modules, all passing:

| Module | Tests |
|---|---|
| `tests/test_schema.py` | Pydantic model validation |
| `tests/test_extractor.py` | HTML parsing & error isolation |
| `tests/test_fetcher.py` | Fetch concurrency, retry logic, metrics |
| `tests/test_database.py` | DB init, upsert, idempotency |

---

## Architecture & Design Decisions

### Project Structure
```
SwarmSpider/
├── fetch/          # aiohttp session management, semaphore, retry/backoff
├── parse/          # BeautifulSoup HTML extraction & Pydantic validation
├── schema/         # Pydantic record definition (ProductRecord)
├── db/             # SQLAlchemy async engine, connection pool, batched UPSERT
├── pipeline/       # Orchestration: fetch → validate → throttled write + backpressure
├── reporting/      # Run summary metrics and structured logging
├── cli/            # main.py (full pipeline) and baseline.py (sequential benchmark)
├── tests/          # 23 unit tests (pytest + pytest-asyncio)
├── mock_server.py  # Local aiohttp test server (120 pages, intentional errors)
└── README.md
```

### Fetch Concurrency Limit — `asyncio.Semaphore(20)`
Firing all 120 requests simultaneously would exhaust local socket file descriptors and replicate a DDoS pattern on any real-world target. A semaphore of **20** was chosen because it provides a **~2x speedup** over sequential while keeping socket usage well within OS limits and being respectful to the target server.

### Database Connection Pool — `pool_size=5, max_overflow=2`
We use `SQLAlchemy` with `aiosqlite` and `AsyncAdaptedQueuePool`. A `pool_size=5` means at most 5 connections are held idle; `max_overflow=2` allows 2 extra connections during traffic bursts, for a hard ceiling of 7 active connections. This prevents connection exhaustion under high concurrency.

### Write Throttling — `asyncio.Semaphore(2)`
Independently of fetch concurrency, only **2 coroutines** may attempt a database write transaction at any time. This prevents write storms when 100+ validated records arrive in a short burst.

### Backpressure — `asyncio.Queue(maxsize=50)`
Validated records flow into a bounded queue (`maxsize=50`). When the write side slows down and the queue fills, `queue.put()` blocks the fetch coroutines automatically — organically applying backpressure up the pipeline without any unbounded in-memory buffering.

### Idempotency — `INSERT ... ON CONFLICT DO UPDATE`
The `url` column is the Primary Key. All writes use SQLite's `ON CONFLICT DO UPDATE` clause so that a retry of a completed-but-unconfirmed write never creates a duplicate row.

### Batched Writes — `batch_size=10`
Records are grouped into batches of 10 before being flushed to the database. This amortises per-transaction overhead (transaction open/commit/close) across 10 rows rather than paying it per-record. Batches smaller than 10 are also flushed eagerly when the queue is empty.

### Per-Page Error Isolation
Both fetch failures and extraction/parse failures are caught per-page. A failed page is logged and written to `rejected_pages.jsonl` with a reason string. The remaining pages are not affected.

---

## Scraped Record Schema

Each successfully scraped and validated page produces a `ProductRecord`:

| Field | Type | Constraints | Source |
|---|---|---|---|
| `url` | `str` | Required, used as unique key | Page URL |
| `title` | `str` | `min_length=1` | `<h1 id="title">` |
| `price` | `float` | `>= 0.0` | `<p id="price">` ($ stripped) |
| `in_stock` | `bool` | Required | `<p id="stock">` text match |
| `description` | `str \| None` | Optional | `<div id="description">` |

---

## Performance Comparison

Both runs against the same 120-page mock server (including pages with intentional 2-second delays and HTTP 500s):

| Mode | Total Time | Throughput | Notes |
|---|---|---|---|
| Sequential (`baseline.py`) | **14.12 s** | 7.79 pages/sec | One request at a time |
| Concurrent (`main.py`) | **6.69 s** | 16.73 items/sec | Semaphore=20 |
| **Speedup** | **2.1×** | — | Bottleneck: slow mock pages |

**Final run counts (120 pages):**

| Stage | Count |
|---|---|
| Pages Requested | 120 |
| Successfully Fetched | 119 |
| Failed to Fetch (after 3 retries) | 1 |
| Successfully Validated | 112 |
| Failed to Parse / Validate | 7 |
| Successfully Written to DB | 112 |
| Failed DB Writes | 0 |

`119 fetched + 1 fetch-failed = 120 ✓`
`112 validated + 7 parse-failed = 119 ✓`

---

## Database Stress Test

To verify graceful degradation under an artificially small pool:

```bash
python cli/main.py --pool-size 2 --write-concurrency 2 --count 120
```

**Result with `pool_size=2`:**

| Metric | Normal Run | Stress Test |
|---|---|---|
| Pool Size | 5 | 2 |
| Write Concurrency | 2 | 2 |
| Total Time | 6.69 s | 8.62 s |
| Items Written | 112 | 113 |
| DB Writes Failed | 0 | 0 |

The pipeline slowed slightly (~29% overhead) but **completed all valid records without crashing or dropping data**. The write-side semaphore queued competing writers, and the bounded `asyncio.Queue` prevented memory from growing unbounded while the DB caught up.

---

## CLI Options Reference

```
python cli/main.py [OPTIONS]

Options:
  --url              Base URL of the target server   [default: http://127.0.0.1:8080]
  --count            Number of pages to fetch        [default: 120]
  --fetch-concurrency  Max concurrent HTTP requests  [default: 20]
  --write-concurrency  Max concurrent DB writes      [default: 2]
  --batch-size       Records per DB write batch      [default: 10]
  --pool-size        DB connection pool size         [default: 5]
  --db-url           SQLAlchemy Async DB URL         [default: sqlite+aiosqlite:///scraper.db]
  --debug            Enable DEBUG-level logging
```
