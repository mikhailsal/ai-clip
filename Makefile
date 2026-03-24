.PHONY: lint format test coverage setup-hooks setup-hotkeys all help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk -F'[:#]' '{ printf "\033[36m%-20s\033[0m %s\n", $$2, $$NF }'

lint: ## Run ruff linter
	@echo "Running ruff check..."
	@ruff check src/ tests/

format: ## Run ruff formatter
	@echo "Running ruff format..."
	@ruff format src/ tests/
	@ruff check --fix src/ tests/

test: ## Run tests with coverage
	@echo "Running tests..."
	@python -m pytest

coverage: ## Show detailed coverage report
	@echo "Running coverage..."
	@python -m pytest --cov-report=html --cov-report=term-missing
	@echo "HTML report: htmlcov/index.html"

setup-hooks: ## Install git pre-commit hook
	@echo "Installing git hooks..."
	@bash setup_hooks.sh

setup-hotkeys: ## Register Cinnamon hotkeys
	@echo "Setting up hotkeys..."
	@python -m ai_clip --setup-hotkeys

all: lint test ## Run lint + test
