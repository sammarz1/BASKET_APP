.PHONY: unit-tests integration-tests format up down logs

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

format:
	.venv/bin/black .
