# Los pasos en este archivo pueden ser usados para su pipeline de Unit testing
# en el caso que usted decida usar Python.

.PHONY: lintfix lintcheck unittest docscopy docsbuild docsclean

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

docsclean:
	find docs/diagrams -name "*.png" -delete
	find docs/apps -name "*.md" -delete

IMAGE_NAME := plantuml/plantuml:latest

docsbuild:
	@echo "Checking Docker image $(IMAGE_NAME)..."
	@if ! docker image inspect "$(IMAGE_NAME)" > /dev/null 2>&1; then \
		echo "Docker image $(IMAGE_NAME) not found. Building..."; \
		cd plantuml-generator && docker build -t "$(IMAGE_NAME)" .; \
	else \
		echo "Docker image $(IMAGE_NAME) already exists. Skipping build."; \
	fi

	@echo "Generating PlantUML diagrams..."
	@docker run --rm \
		-e PLANTUML_LIMIT_SIZE=8192 \
		-v "$(PWD)/docs/diagrams:/workspace" \
		-w /workspace \
		"$(IMAGE_NAME)" \
		"**.puml"

# ------------------------------------------------------------
# Copy application README files into the documentation tree.
#
# The application READMEs remain in their original locations.
# Copies are created under docs/apps/ so Jekyll can process them.
# ------------------------------------------------------------

docscopy:
	@echo "Copying application README files..."

	@mkdir -p docs/apps

	@cp users_app/README.md docs/apps/users_app.md
	@cp routes_app/README.md docs/apps/routes_app.md
	@cp posts_app/README.md docs/apps/posts_app.md
	@cp offers_app/README.md docs/apps/offers_app.md
	@cp scores_app/README.md docs/apps/scores_app.md
	@cp rf003_create_post_app/README.md docs/apps/rf003_create_post_app.md
	@cp rf004_create_offer_app/README.md docs/apps/rf004_create_offer_app.md
	@cp rf005_query_post_app/README.md docs/apps/rf005_query_post_app.md

	@echo "Application documentation copied successfully."