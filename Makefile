.PHONY: quality style test

quality:
	ruff check .
	ruff format --check .

style:
	ruff check --fix .
	ruff format .

test:
	pytest -sv ./src/
