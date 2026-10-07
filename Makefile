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
	@echo "  make desktop-run                                   Launch the desktop client (MODE=ui for the real GUI; default prints the version)"
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

# Desktop client (wp-01): host-side lint/test, no Docker involved.
.PHONY: desktop-lint desktop-test desktop-install desktop-run

desktop-lint:
	venv/bin/ruff check desktop/src desktop/tests

desktop-test:
	venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q

desktop-install:
	uv sync --project desktop

# Launch the desktop client. Default is a headless sanity invocation
# (--version, offscreen Qt platform): it proves the entry point works on a
# display-less host without opening a window. MODE=ui drops the offscreen
# platform and runs the real GUI, which needs a display.
desktop-run:
	@if [ "$(MODE)" = "ui" ]; then \
		uv run --project desktop limes-desktop; \
	else \
		QT_QPA_PLATFORM=offscreen uv run --project desktop limes-desktop --version; \
	fi
