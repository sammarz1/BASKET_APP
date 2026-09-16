.PHONY: unit-tests integration-tests format

unit-tests:
	pytest unit-tests

integration-tests:
	pytest integration-tests

format:
	black format .
