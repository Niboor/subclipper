# Python virtual environment
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Docker
DOCKER_IMAGE = subclipper
DOCKER_TAG = latest

# Environment variables
SEARCH_PATH ?= $(shell pwd)/subclipper/samples
SHOW_NAME ?= Subclipper Test

.PHONY: help venv install test run docker-build docker-run clean tailwind

help:
	@echo "Available targets:"
	@echo "  venv          - Create Python virtual environment"
	@echo "  install       - Install Python dependencies"
	@echo "  tailwind      - Install and compile Tailwind CSS"
	@echo "  test          - Run tests"
	@echo "  run           - Start development server"
	@echo "  docker-build  - Build Docker image"
	@echo "  docker-run    - Run Docker container"
	@echo "  clean         - Remove virtual environment and build artifacts"

# Virtual environment targets
venv:
	@echo "Creating Python virtual environment..."
	python -m venv $(VENV)
	@echo "Virtual environment created. Run 'source $(VENV)/bin/activate' to activate it."

install: venv
	@echo "Installing dependencies..."
	$(PIP) install -e ".[dev]"
	@echo "Dependencies installed."

# Setup yarn frontend dependencies
yarn:
	@echo "Installing dependencies with yarn..."
	yarn
	@echo "Bundling TypeScript..."
	yarn build

# Tailwind CSS targets
# tailwind:
# 	@echo "Installing Tailwind CSS dependencies..."
# 	yarn
# 	@echo "Compiling Tailwind CSS..."
# 	npx tailwindcss -i ./subclipper/app/static/main.css -o ./subclipper/app/static/tailwind.css

# Development targets
test:
	@echo "Running tests..."
	$(PYTHON) -m pytest subclipper/tests/ -v

run: yarn
	@echo "Starting development server..."
	FLASK_APP=subclipper.app \
	FLASK_ENV=development \
	SEARCH_PATH=$(SEARCH_PATH) \
	SHOW_NAME="$(SHOW_NAME)" \
	$(PYTHON) -m flask run --debug

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run:
	@echo "Running Docker container..."
	docker run -p 8000:8000 \
		-e SEARCH_PATH=/app/subclipper/samples \
		-e SHOW_NAME="$(SHOW_NAME)" \
		$(DOCKER_IMAGE):$(DOCKER_TAG)

# Cleanup
clean:
	@echo "Cleaning up..."
	rm -rf $(VENV)
	rm -rf *.egg-info
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf node_modules
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete."
