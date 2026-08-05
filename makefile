# Los pasos en este archivo pueden ser usados para su pipeline de Unit testing
# en el caso que usted decida usar Python.

.PHONY: lintfix lintcheck unittest

lintfix:
	poetry --directory=${DIR} install
	poetry --directory=${DIR} run black .
	poetry --directory=${DIR} run isort . --profile black
	poetry --directory=${DIR} run bandit -c pyproject.toml -r .
	poetry --directory=${DIR} run ruff check --fix

lintcheck:
	poetry --directory=${DIR} install
	poetry --directory=${DIR} run black --check .
	poetry --directory=${DIR} run isort --check . --profile black
	poetry --directory=${DIR} run bandit -c pyproject.toml -r .
	poetry --directory=${DIR} run ruff check

unittest:
	poetry --directory=${DIR} install
	poetry --directory=${DIR} run pytest --cov=src -v -s --cov-fail-under=70 --cov-report term-missing

# Agregue nuevas a partir de esta línea