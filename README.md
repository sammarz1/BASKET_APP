# Basket App

Web application and ETL pipeline for basketball analytics (NBA & EuroLeague).

## Getting Started

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose

### 2. Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt
```

### 3. Local Storage (MinIO)

Start the local S3-compatible MinIO object storage in Docker:

```bash
make up
```

- **S3 API Endpoint**: `http://localhost:9000`
- **Web Console UI**: [http://localhost:9001](http://localhost:9001)
  - **User**: `minioadmin`
  - **Password**: `minioadmin`
- **Default Bucket**: `bronze` (auto-provisioned on startup)

Verify the connection and upload/download:

```bash
make verify-storage
```

To stop MinIO:

```bash
make down
```

## Extracting Data (Bronze)

Extractors fetch raw API responses and store them byte-for-byte (gzipped) in the
bronze bucket, with provenance (source URL, HTTP status, retrieval time, season…)
as S3 object metadata. Runs are idempotent: existing keys are skipped unless
`--overwrite` is given.

Key convention (Hive-style partitions for the silver layer):

```text
{league}/{endpoint}/season={season}/[date=YYYY-MM-DD/]{name}.json.gz
```

```bash
# EuroLeague: all games for a season (season code: E=EuroLeague, U=EuroCup)
make extract LEAGUE=euroleague ENDPOINT=games SEASON=E2025

# NBA via ESPN public API: one scoreboard object per day
make extract LEAGUE=nba ENDPOINT=espn_scoreboard SEASON=2024-25 ARGS="--start 2025-04-01 --end 2025-04-03"

# NBA official CDN schedule — cdn.nba.com / stats.nba.com are geo-blocked outside the US
make extract LEAGUE=nba ENDPOINT=schedule SEASON=2025-26

# List what is in bronze
make list-bronze PREFIX=nba/
```

Or directly: `PYTHONPATH=src python -m basket_app extract --help`.

To add an endpoint: subclass `BaseExtractor` (set `league`, `endpoint`, implement
`iter_requests()`), then register it in `basket_app/extract/registry.py`.

## Available Commands

Run commands using `make`:

```bash
# Start MinIO storage
make up

# Stop MinIO storage
make down

# View MinIO container logs
make logs

# Verify Bronze storage connection and test I/O
make verify-storage

# Run unit tests
make unit-tests

# Run integration tests (against live MinIO)
make integration-tests

# Extract an endpoint into bronze / list bronze keys
make extract LEAGUE=... ENDPOINT=... SEASON=... [ARGS=...]
make list-bronze [PREFIX=...]

# Format code
make format
```

## Project Structure

```text
├── Makefile                   # Automation commands
├── docker-compose.yml         # Local MinIO S3 object storage
├── pyproject.toml             # Project configuration & tool settings
├── .env.template              # Environment variables template
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development & test dependencies
├── src/
│   └── basket_app/
│       ├── cli.py             # `python -m basket_app extract|list`
│       ├── core/
│       │   ├── config.py      # Storage + HTTP settings (pydantic-settings, .env)
│       │   ├── http.py        # Session with retries/backoff, timeouts, rate limiting
│       │   ├── logging.py     # Logging setup
│       │   └── storage.py     # BronzeStorage S3 client (raw bytes / JSON, cloud-agnostic)
│       └── extract/
│           ├── base.py        # BaseExtractor: fetch → skip-if-exists → put_raw_bytes
│           ├── registry.py    # (league, endpoint) → extractor class
│           ├── nba/           # schedule (cdn.nba.com), espn_scoreboard
│           └── euroleague/    # games (api-live.euroleague.net v2)
├── scripts/
│   └── verify_bronze_storage.py # Storage verification script
├── unit-tests/                # Unit tests
└── integration-tests/         # Integration tests
```
