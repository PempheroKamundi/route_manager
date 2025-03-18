# Variables
PYTHON = python
PYTEST = $(PYTHON) -m pytest
MYPY = mypy
PRECOMMIT = pre-commit

# Default target
.PHONY: all
all: help

# Help target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  test                - Run tests using pytest"
	@echo "  test-verbose        - Run tests with verbose output"
	@echo "  test-quiet          - Run tests with quiet output"
	@echo "  test-with-coverage  - Run tests with coverage report"
	@echo "  test-debug          - Run tests with debug information"
	@echo "  test-specific       - Run a specific test"
	@echo "  test-file           - Run tests in a specific file"
	@echo "  type-check          - Run mypy for type checking"
	@echo "  pre-commit          - Run pre-commit hooks on all files"
	@echo "  clean               - Clean up generated files"

# Run tests with default options
.PHONY: test
test:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing

# Run tests with verbose output
.PHONY: test-verbose
test-verbose:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing -v

# Run tests with quiet output
.PHONY: test-quiet
test-quiet:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing -q

# Run tests with coverage reporting
.PHONY: test-with-coverage
test-with-coverage:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=html

# Run tests with debug information (for print statements)
.PHONY: test-debug
test-debug:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing -s

# Run a specific test by name
.PHONY: test-specific
test-specific:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing -k 'test_name'

# Run tests in a specific file
.PHONY: test-file
test-file:
	$(PYTEST) --maxfail=5 --disable-warnings --cov=. --cov-report=term-missing $(TEST_DIR)/test_file.py

# Type checking with mypy
.PHONY: type-check
type-check:
	$(MYPY) .

# Run pre-commit hooks
.PHONY: pre-commit
pre-commit:
	$(PRECOMMIT) run --all-files

# Clean up files
.PHONY: clean
clean:
	find . -name "__pycache__" -exec rm -rf {} +
	find . -name "*.pyc" -exec rm -f {} +
