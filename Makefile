.PHONY: unit-tests integration-tests format up down logs verify-storage extract list-bronze

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

unit-tests:
	.venv/bin/pytest unit-tests

integration-tests:
	.venv/bin/pytest integration-tests

verify-storage:
	PYTHONPATH=src .venv/bin/python scripts/verify_bronze_storage.py

format:
	.venv/bin/black .

# Usage: make extract LEAGUE=nba ENDPOINT=schedule SEASON=2025-26 [ARGS=--overwrite]
extract:
	PYTHONPATH=src .venv/bin/python -m basket_app extract $(LEAGUE) $(ENDPOINT) --season $(SEASON) $(ARGS)

# Usage: make list-bronze PREFIX=nba/
list-bronze:
	PYTHONPATH=src .venv/bin/python -m basket_app list $(PREFIX)
