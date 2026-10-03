.PHONY: help install lint format typecheck test check analyse clean

PYTHON ?= python
CONFIG ?= config/experiment.yaml

help:  ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

install:  ## Install the package and dev tools in editable mode
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install

lint:  ## Lint and check formatting
	ruff check src tests
	ruff format --check src tests

format:  ## Auto-fix lint issues and format code
	ruff check --fix src tests
	ruff format src tests

typecheck:  ## Static type checks
	mypy src

test:  ## Run the test suite with coverage
	pytest --cov --cov-report=term

check: lint typecheck test  ## Everything CI runs

analyse:  ## Run the analysis and write reports/
	abtest run --config $(CONFIG)

clean:  ## Remove generated files
	rm -rf reports .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov build dist
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
