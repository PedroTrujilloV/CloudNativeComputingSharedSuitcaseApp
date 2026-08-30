# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Entrega 1] - 2026-08-30

### Added
- Initial set of files for **Entrega 1** (commit `0cb591c`, PR #33 by `pe.trujillo`),
  covering the microservices, domain docs, Kubernetes manifests, and CI workflows
  (198 files, ~19,700 insertions).

#### Microservices
- **offers_app**: FastAPI service with Clean Architecture layout (`domain` / `adapters` /
  `entrypoints`), offer repository adapter, configuration, error handling, unit + API tests,
  Postman collection, `Dockerfile`, and `pyproject.toml`/`poetry.lock`.
- **posts_app**: FastAPI service for publications with database adapter and repository,
  `create_publication` use case, API router and schemas, unit tests, `Dockerfile`,
  and `pyproject.toml`/`poetry.lock`.
- **routes_app**: FastAPI service for routes with domain models (`route`, `schemas`),
  route validation service, database adapter, API router, extensive unit tests
  (including Postman/pytest suites), `Dockerfile`, and `pyproject.toml`/`poetry.lock`.
- **users_app**: FastAPI service for users with database adapter, security adapters
  (password hashing, token generation), auth/user use cases, API router and schemas,
  unit tests, `Dockerfile`, and `pyproject.toml`/`poetry.lock`.

#### Documentation
- `docs/README.md`, `docs/TeamRules.md`, and the four view documents:
  `deployment-view.md`, `development-view.md`, `functional-view.md`, `information-view.md`.
- PlantUML diagrams and their generated PNGs: `components.puml/png`,
  `deployment.puml/png`, `entities.puml/png`, `networks.puml/png`.
- `plantuml-generator` service (`Dockerfile`, `entrypoint.sh`, `.dockerignore`) for
  rendering the diagrams.
- Root `README.md` updated and `old_README.md` preserved.

#### Kubernetes
- Deployment manifests: `offers-app.yaml`, `posts-app.yaml`, `routes-app.yaml`,
  `users-app.yaml`.
- Network policies: `offers-network-policy.yaml`, `posts-network-policy.yaml`,
  `routes-network-policy.yaml`, `users-network-policy.yaml`.

#### CI / Workflows & Tooling
- Updated GitHub Actions workflows: `ci_evaluador_unit.yml`, `ci_pipeline.yml`,
  and new `pages.yml`.
- Updated `config.yaml`, `makefile`, and `.gitignore` to support the new structure.

[Unreleased]: https://github.com/Uniandes-Is4103/202614-grupo33-proyecto/compare/v0.1.0...HEAD
[Entrega 1]: https://github.com/Uniandes-Is4103/202614-grupo33-proyecto/compare/v0.1.0...0cb591c
