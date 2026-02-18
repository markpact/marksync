.PHONY: test install clean lint format

test:
	. .venv/bin/activate && pytest tests/ -v

install:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -e ".[dev]"

clean:
	rm -rf .venv
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

lint:
	. .venv/bin/activate && ruff check .

format:
	. .venv/bin/activate && ruff format .

dev: install
	. .venv/bin/activate && pre-commit install
