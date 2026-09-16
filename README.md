# Basket App

Web application and ETL pipeline.

## Getting Started

### 1. Prerequisites
- Python 3.11+

### 2. Setup Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install development dependencies
pip install -r requirements-dev.txt
```

## Available Commands

Run commands using `make`:

```bash
# Run unit tests
make unit-tests

# Run integration tests
make integration-tests

# Format code
make format
```

## Project Structure

```text
├── Makefile                # Automation commands
├── pyproject.toml          # Project configuration & tool settings
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development & test dependencies
├── unit-tests/             # Unit tests
└── integration-tests/      # Integration tests
```
