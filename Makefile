.PHONY: test lint typecheck shell-check check

PYTHONPATH := src

test:
	PYTHONPATH=$(PYTHONPATH) python3 -m unittest discover -s tests -v

lint:
	ruff format --check src tests
	ruff check src tests

typecheck:
	mypy --strict src/nos_server

shell-check:
	bash -n docker-entrypoint.sh scripts/*.sh
	./scripts/test-shell-behavior.sh

check: lint typecheck test shell-check
	python3 -m compileall -q src tests
