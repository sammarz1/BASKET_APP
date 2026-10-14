# Basket App 🏀

[![CI](https://github.com/sammarz1/BASKET_APP/actions/workflows/ci.yml/badge.svg)](https://github.com/sammarz1/BASKET_APP/actions/workflows/ci.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue?logo=docker)](https://github.com/sammarz1/BASKET_APP/pkgs/container/basket-app)
[![Python 3.11 | 3.12](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Architecture: Medallion](https://img.shields.io/badge/architecture-medallion%20lakehouse-orange.svg)](#architecture-overview)

A production-grade basketball analytics data platform and ETL pipeline ingesting **all available historical and operational data** for the **NBA** and **EuroLeague**.

Built on a **Medallion Lakehouse Architecture** (Bronze $\rightarrow$ Silver $\rightarrow$ Gold) with immutable raw data ingestion into S3 / MinIO object storage.

---

## 🏛️ Architecture Overview

The platform uses a medallion data lakehouse pattern:

```text
 ┌────────────────┐       ┌────────────────┐
 │ EuroLeague API │       │    ESPN API    │
 └───────┬────────┘       └───────┬────────┘
         │                        │
         ▼                        ▼
 ┌─────────────────────────────────────────┐
 │             BRONZE LAYER                │
 │  • Immutable Raw Payloads (.json.gz)    │
 │  • Hive Partitioning (league/season/..) │
 │  • Source Provenance & Ingestion Meta   │
 │  • S3 / MinIO Object Storage            │
 └───────────────────┬─────────────────────┘
                     │
                     ▼
 ┌─────────────────────────────────────────┐
 │             SILVER LAYER                │
 │  • Cleansed, Typed, Deduplicated Tables │
 │  • Parquet on MinIO / DuckDB            │
 └───────────────────┬─────────────────────┘
                     │
                     ▼
 ┌─────────────────────────────────────────┐
 │              GOLD LAYER                 │
 │  • Advanced Metrics (PIR, eFG%, TS%)    │
 │  • Shot Charts, Boxscore Views & Models │
 └─────────────────────────────────────────┘
```

### Bronze Lakehouse Principles
- **Byte-Identical Raw Ingestion**: Responses are written as received, compressed with `gzip` (`.json.gz`).
- **Audit & Provenance**: Every object carries S3 metadata tags (`ingested_at`, `source_url`, `status_code`, etc.).
- **Idempotency**: All extractions check for existing objects and skip by default (`--overwrite` to force re-fetch).
- **Scalable Discovery**: Automatically resolves games and clubs from calendar endpoints with dependency ordering.

---

## 📊 Ingestion Coverage

### 🇪🇺 EuroLeague
Base API: `https://api-live.euroleague.net/v2`

| Endpoint | S3 Key Partition Pattern | Description |
| :--- | :--- | :--- |
| `games` | `euroleague/games/season={season}/games.json.gz` | Season calendar, round codes, game status |
| `clubs` | `euroleague/clubs/season={season}/clubs.json.gz` | Participating clubs, team codes, logos, arenas |
| `roster` | `euroleague/roster/season={season}/club_code={club}/roster.json.gz` | Full team rosters, player IDs, positions |
| `boxscore` | `euroleague/boxscore/season={season}/game_code={code}/boxscore.json.gz` | Boxscores, minutes, PIR, shooting splits |
| `playbyplay` | `euroleague/playbyplay/season={season}/game_code={code}/playbyplay.json.gz` | Event stream: fouls, assists, substitutions |
| `shots` | `euroleague/shots/season={season}/game_code={code}/shots.json.gz` | Shot coordinates $(x, y)$, shot type, outcome |
| `standings` | `euroleague/standings/season={season}/standings.json.gz` | Regular season league standings & point diffs |
| `people` | `euroleague/people/season={season}/people.json.gz` | Complete roster of players, coaches, staff |

### 🇺🇸 NBA
Primary Provider: ESPN Global APIs (unrestricted, high availability)

| Endpoint | S3 Key Partition Pattern | Description |
| :--- | :--- | :--- |
| `scoreboard` | `nba/espn_scoreboard/season={season}/date={date}/scoreboard.json.gz` | Daily scoreboards, game lines, venues |
| `summary` | `nba/summary/season={season}/game_id={id}/summary.json.gz` | Boxscore, player stats, play-by-play, odds |
| `teams` | `nba/teams/season={season}/teams.json.gz` | All 30 franchises, logos, conference/division |
| `roster` | `nba/roster/season={season}/team_id={id}/roster.json.gz` | Full active & reserve rosters, contracts |
| `standings` | `nba/standings/season={season}/standings.json.gz` | Conference standings, streaks, records |
| `player` | `nba/player/player_id={id}/profile.json.gz` | Player bio, height, weight, draft info |
| `schedule` | `nba/schedule/season={season}/schedule.json.gz` | Season master schedule |

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose

### 2. Environment Setup

```bash
# Clone and enter directory
cd BASKET_APP

# Create and activate virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install package in editable mode with development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

### 3. Start Local Storage (MinIO)

Start the local S3-compatible MinIO object storage in Docker:

```bash
make up
```

- **S3 API Endpoint**: `http://localhost:9000`
- **Web Console UI**: [http://localhost:9001](http://localhost:9001)
  - **Username**: `minioadmin`
  - **Password**: `minioadmin`
- **Default Bucket**: `bronze` (auto-provisioned on startup)

To stop storage:
```bash
make down
```

---

## 🛠️ CLI Operations & Workflows

The `basket-app` CLI provides commands for operational runs, historical backfills, lakehouse audits, and raw extractions.

### 1. Operational Daily Ingestion (`daily`)
Runs daily operational pipeline for active seasons, ingesting yesterday's scoreboards, game boxscores/summaries, and refreshing standings:

```bash
# Ingest both NBA and EuroLeague for yesterday
basket-app daily

# Target a specific date
basket-app daily --date 2024-11-02

# Catch up multiple days of backlogged games
basket-app daily --days-back 7

# Run only NBA and refresh rosters
basket-app daily --league nba --refresh-rosters
```

### 2. Historical Backfill Orchestration (`backfill`)
Bulk-ingests multiple endpoints across single seasons or season spans with automatic topological dependency resolution:

```bash
# Backfill an entire EuroLeague season
basket-app backfill euroleague --season E2024

# Backfill specific endpoints only
basket-app backfill euroleague --season E2024 --include games,clubs,roster

# Exclude heavy shot coordinate data
basket-app backfill euroleague --season E2024 --exclude shots,playbyplay

# Multi-season historical backfill
basket-app backfill nba --start-season 2022-23 --end-season 2024-25

# Safe test run with item limit per endpoint
basket-app backfill nba --season 2024-25 --limit 5
```

### 3. Lakehouse Audit & Coverage Tooling (`audit`)
Inspects storage health, calculates completeness percentages, and detects missing games or rosters:

```bash
# Full audit across all leagues and seasons
basket-app audit

# Audit a specific league and season
basket-app audit --league euroleague --season E2024

# Detailed view showing all missing game IDs
basket-app audit --league nba --detailed

# Machine-readable JSON output (for CI/CD or monitoring)
basket-app audit --json
```

### 4. Single Endpoint Extraction (`extract`)
Directly fetch any single endpoint:

```bash
# Extract EuroLeague games calendar
basket-app extract euroleague games --season E2024

# Extract NBA scoreboards for a date range
basket-app extract nba scoreboard --season 2024-25 --start 2024-11-01 --end 2024-11-05

# Extract team rosters
basket-app extract nba roster --season 2024-25
```

### 5. Utility Commands
```bash
# List all registered extractors
basket-app extractors

# List objects stored in Bronze
basket-app list euroleague/boxscore/
```

---

## 🧪 Testing & Quality Assurance

The test suite includes comprehensive unit tests and live integration tests verifying MinIO read/write, gzip compression, and metadata tags:

```bash
# Run all unit tests
make unit-tests

# Run live integration tests (requires 'make up')
make integration-tests

# Run entire test suite
make test

# Run tests with terminal coverage report
make test-cov

# Check linting and formatting (Ruff + Black)
make lint

# Auto-fix linting and format code
make format
```

---

## 🔄 CI/CD & Delivery Workflows

The repository uses native, zero-cost GitHub Actions workflows:

| Workflow | Trigger | Description |
| :--- | :--- | :--- |
| **`CI`** (`ci.yml`) | Pull Request & Push (`main`) | Lints code (Ruff + Black), matrix tests (Python 3.11 & 3.12) against live MinIO service container, posts Markdown coverage summaries to Job Summaries, and validates CLI audit. Cancel-in-progress enabled. |
| **`CD - Container`** (`docker.yml`) | Push (`main`), Tags (`v*`), PRs | Validates multi-platform Docker container build (`linux/amd64`, `linux/arm64`) with GitHub Actions layer caching. Automatically publishes images to **GitHub Container Registry (GHCR)** on merges to `main` and semver releases. |
| **`DataOps Ingestion`** (`scheduled-ingestion.yml`) | Cron (`06:00 UTC`), `workflow_dispatch` | Scheduled daily ETL runner executing `basket-app daily` and publishing Bronze audit logs to the workflow summary. |

### Running via Docker

You can pull and run the published container directly from GHCR:

```bash
# Pull the latest image
docker run --rm ghcr.io/sammarz1/basket_app:latest --help

# Run daily catch-up ingestion with MinIO/S3 credentials
docker run --rm \
  -e S3_ENDPOINT_URL=http://minio:9000 \
  -e S3_ACCESS_KEY_ID=minioadmin \
  -e S3_SECRET_ACCESS_KEY=minioadmin \
  ghcr.io/sammarz1/basket_app:latest daily --days-back 1
```

## 🧩 Adding New Endpoints

The architecture is designed for trivial extensibility. To add a new data endpoint:

1. Create an extractor subclassing `BaseExtractor` in `src/basket_app/extract/<league>/<name>.py`:
   ```python
   from typing import Iterable
   from basket_app.extract.base import BaseExtractor, ExtractRequest

   class MyNewExtractor(BaseExtractor):
       league = "nba"
       endpoint = "injuries"

       def iter_requests(self) -> Iterable[ExtractRequest]:
           yield ExtractRequest(
               url="https://...",
               key=self.build_key(name="injuries"),
               metadata={"season": self.season},
           )
   ```

2. Register the extractor in `src/basket_app/extract/registry.py`:
   ```python
   register_extractor(MyNewExtractor)
   ```

The new endpoint immediately becomes accessible in `basket-app extract`, `basket-app backfill`, and the audit tooling without further changes.
