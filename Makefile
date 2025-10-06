# Python virtual environment
VENV = .venv
PYTHON = $(VENV)/bin/python
PIP = $(VENV)/bin/pip

# Docker
DOCKER_IMAGE = subclipper
DOCKER_TAG = latest

# Environment variables
SEARCH_PATH ?= $(shell pwd)/src/samples

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

# Development targets
test:
	@echo "Running tests..."
	$(PYTHON) -m pytest src/tests/ -v

run: yarn
	@echo "Starting development server..."
	FLASK_APP=src.app \
	FLASK_ENV=development \
	SEARCH_PATH=$(SEARCH_PATH) \
	# $(PYTHON) -m flask run --debug
	gunicorn "src.app:create_app()" -w 1 --threads 10 -b 127.0.0.1:5000

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

docker-run:
	@echo "Running Docker container..."
	docker run -p 8000:8000 \
		-e SEARCH_PATH=/app/src/samples \
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
