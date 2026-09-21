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

To stop MinIO:

```bash
make down
```

## Bronze Layer

This is a skeleton: `core/http.py` (retrying HTTP client) and `core/storage.py`
(S3/MinIO bronze storage client) are ready to use, but there are no extractors
yet. Build the bronze-layer ingestion (fetching raw API responses and writing
them to the bronze bucket) on top of these.

## Available Commands

Run commands using `make`:

```bash
# Start MinIO storage
make up

# Stop MinIO storage
make down

# View MinIO container logs
make logs

# Run unit tests
make unit-tests

# Run integration tests (against live MinIO)
make integration-tests

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
│       ├── cli.py             # CLI entry point skeleton
│       └── core/
│           ├── config.py      # Settings (pydantic-settings, .env)
│           ├── http.py        # HttpClient: retries/backoff, timeout, rate limiting
│           └── storage.py     # BronzeStorage S3 client (raw bytes / JSON, cloud-agnostic)
├── unit-tests/                # Unit tests
└── integration-tests/         # Integration tests
```
