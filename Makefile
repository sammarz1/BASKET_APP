.PHONY: unit-tests integration-tests test format up down logs audit daily

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

format:
	.venv/bin/black .

audit:
	.venv/bin/basket-app audit

daily:
	.venv/bin/basket-app daily
