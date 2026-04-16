.PHONY: quality style test

quality:
	uvx ruff check .
	uvx ruff format --check .

style:
	uvx ruff check --fix .
	uvx ruff format .

test:
	uv run pytest -sv ./src/
