# LIMES Makefile | v2.1.0 | testing-phase operational commands
# Stack administration still uses Docker; API consumers do not need Docker access.
# Model calls record passive spend. No mandatory budget envelopes.
COMPOSE ?= docker compose --env-file config/settings.env --env-file config/secrets.env
REMOTE ?= venv/bin/limes remote run

.PHONY: help up down bootstrap-db ingest ingest-all backfill reextract \
	select-models evaluate migrate backup stamp-embeddings

help:
	@echo "LIMES — ontology-driven knowledge graph."
	@echo
	@echo "Targets (Doc 2 §8.14, Doc 1 §6.6):"
	@echo "  make up                                             Start the three services (builds the images on first run)"
	@echo "  make down                                           Stop and remove the containers"
	@echo "  make bootstrap-db                                   No-op: C-01 offers no roles; provisioning runs on every context build"
	@echo "  make ingest SOURCE=<id>                             Ingest one source (e.g. gisco_nuts, gleif)"
	@echo "  make ingest-all                                     Ingest every registered source"
	@echo "  make backfill SOURCE=<id> DAYS=<n>     Historical load with passive cost accounting"
	@echo "  make reextract PROMPT_VERSION=<v>      Re-extract archived content"
	@echo "  make select-models STAGE=provisional            Stage 1: rank and pin by criteria (confirmation optional)"
	@echo "  make select-models STAGE=measured               Stage 2: measure the candidates against the gold set"
	@echo "  make evaluate EVALUATION=resolution                  Measure extraction quality against the gold set; records baseline.json"
	@echo "  make migrate ONTOLOGY_VERSION=<v>                   Apply the migration to the target ontology version"
	@echo "  make backup                                         Offline Neo4j dump into the archive volume (Doc 2 §13.6)"
	@echo "  make stamp-embeddings                              One-shot: fill null label_embeddings before the first backfill (§13.3)"
	@echo "  make desktop-run                                    Serve the web desktop launcher (MODE=ui; default prints the version)"
	@echo "  make web-check                                      Typecheck + vitest + lint + build the SPA (desktop/web)"
	@echo
	@echo "Bootstrap sequence: README.md, or Technical Specification §13.3."

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

bootstrap-db:
	@echo "bootstrap-db: nothing to do — Community Edition offers no roles (C-01),"
	@echo "and provisioning runs on every context build. See README.md for the bootstrap."

ingest:
	@test -n "$(SOURCE)" || { echo "error: ingest requires SOURCE=<id>"; exit 2; }
	$(REMOTE) ingest --source $(SOURCE)

ingest-all:
	$(REMOTE) ingest-all

backfill:
	@test -n "$(SOURCE)" || { echo "error: backfill requires SOURCE=<id>"; exit 2; }
	@test -n "$(DAYS)" || { echo "error: backfill requires DAYS=<n>"; exit 2; }
	$(REMOTE) backfill --source $(SOURCE) --days $(DAYS)

reextract:
	@test -n "$(PROMPT_VERSION)" || { echo "error: reextract requires PROMPT_VERSION=<v>"; exit 2; }
	$(REMOTE) reextract --version $(PROMPT_VERSION)

select-models:
	$(REMOTE) select-models --stage $(or $(STAGE),provisional)

evaluate:
	$(REMOTE) evaluate --evaluation $(or $(EVALUATION),extraction)

migrate:
	@test -n "$(ONTOLOGY_VERSION)" || { echo "error: migrate requires ONTOLOGY_VERSION=<v>"; exit 2; }
	$(REMOTE) migrate --version $(ONTOLOGY_VERSION)

backup:
	$(REMOTE) backup

stamp-embeddings:
	$(REMOTE) stamp-embeddings

# Web desktop (DC-17): host-side lint/test, no Docker involved. The Python
# launcher is a workspace member of the root venv; the SPA needs pnpm.
.PHONY: desktop-lint desktop-test desktop-integration desktop-install desktop-run \
        web-install web-check

desktop-lint:
	venv/bin/ruff check desktop/src desktop/tests

desktop-test:
	venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q

desktop-integration:
	venv/bin/python -m pytest desktop/tests/integration -q

desktop-install:
	UV_PROJECT_ENVIRONMENT=venv uv sync --frozen --all-packages

# Launch the web desktop launcher. Default is a headless sanity invocation
# (--version): it proves the entry point works on a display-less host without
# binding. MODE=ui serves the real launcher (built SPA + /api proxy) on
# loopback — build the SPA first (`make web-check` or `pnpm -C desktop/web build`).
desktop-run:
	@if [ "$(MODE)" = "ui" ]; then \
		venv/bin/limes-desktop; \
	else \
		venv/bin/limes-desktop --version; \
	fi

web-install:
	pnpm -C desktop/web install --frozen-lockfile

web-check:
	pnpm -C desktop/web exec tsc -b
	pnpm -C desktop/web exec vitest run
	pnpm -C desktop/web exec eslint src
	pnpm -C desktop/web build
