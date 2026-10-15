.PHONY: unit-tests integration-tests test test-cov lint format up down logs audit daily backfill-history

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

test:
	.venv/bin/pytest

test-cov:
	.venv/bin/pytest --cov=basket_app --cov-report=term-missing

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

format:
	.venv/bin/ruff check --fix .
	.venv/bin/black .

audit:
	.venv/bin/basket-app audit

daily:
	.venv/bin/basket-app daily

backfill-history:
	./scripts/backfill_history.sh

