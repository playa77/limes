# LIMES — Makefile | v2.0.0 | introduced by WP-01 (stub), full target set by WP-38
# The operator's primary interface (Doc 1 §6.6, Doc 2 §8.14). Every command
# runs inside the worker container via `docker compose exec`; configuration
# flows from ./.env (D-57). `backfill` and `reextract` refuse to run
# without an explicit BUDGET — the envelope that keeps the monthly ceiling
# untouched (Doc 1 §9.2, AC-15).

.PHONY: help up down bootstrap-db ingest ingest-all backfill reextract \
	select-models evaluate migrate backup stamp-embeddings

help:
	@echo "LIMES — ontology-driven knowledge graph."
	@echo
	@echo "Targets (Doc 2 §8.14, Doc 1 §6.6):"
	@echo "  make up                                             Start the four services (builds the images on first run)"
	@echo "  make down                                           Stop and remove the containers"
	@echo "  make bootstrap-db                                   No-op: C-01 offers no roles; provisioning runs on every context build"
	@echo "  make ingest SOURCE=<id>                             Ingest one source (e.g. gisco_nuts, gleif)"
	@echo "  make ingest-all                                     Ingest every registered source"
	@echo "  make backfill SOURCE=<id> DAYS=<n> BUDGET=<eur>     Historical load under an explicit envelope (BUDGET mandatory)"
	@echo "  make reextract PROMPT_VERSION=<v> BUDGET=<eur>      Re-extract archived content (BUDGET mandatory)"
	@echo "  make select-models ARGS=\"--provisional\"            Stage 1: rank and pin by criteria (operator confirmation)"
	@echo "  make select-models ARGS=\"--measured\"               Stage 2: measure the candidates against the gold set"
	@echo "  make evaluate ARGS=\"--resolution\"                  Measure extraction quality against the gold set; records baseline.json"
	@echo "  make migrate ONTOLOGY_VERSION=<v>                   Apply the migration to the target ontology version"
	@echo "  make backup                                         Offline Neo4j dump into the archive volume (Doc 2 §13.6)"
	@echo "  make stamp-embeddings                              One-shot: fill null label_embeddings before the first backfill (§13.3)"
	@echo "  make desktop-run                                   Launch the desktop client (MODE=ui for the real GUI; default prints the version)"
	@echo
	@echo "Bootstrap sequence: README.md, or Technical Specification §13.3."

up:
	docker compose up -d

down:
	docker compose down

bootstrap-db:
	@echo "bootstrap-db: nothing to do — Community Edition offers no roles (C-01),"
	@echo "and provisioning runs on every context build. See README.md for the bootstrap."

ingest:
	@test -n "$(SOURCE)" || { echo "error: ingest requires SOURCE=<id>"; exit 2; }
	docker compose exec worker limes ingest --source $(SOURCE)

ingest-all:
	docker compose exec worker limes ingest-all

backfill:
	@test -n "$(SOURCE)" || { echo "error: backfill requires SOURCE=<id>"; exit 2; }
	@test -n "$(DAYS)" || { echo "error: backfill requires DAYS=<n>"; exit 2; }
	@test -n "$(BUDGET)" || { echo "error: backfill requires BUDGET=<eur>"; exit 2; }
	docker compose exec worker limes backfill --source $(SOURCE) --days $(DAYS) --budget $(BUDGET)

reextract:
	@test -n "$(PROMPT_VERSION)" || { echo "error: reextract requires PROMPT_VERSION=<v>"; exit 2; }
	@test -n "$(BUDGET)" || { echo "error: reextract requires BUDGET=<eur>"; exit 2; }
	docker compose exec worker limes reextract --prompt-version $(PROMPT_VERSION) --budget $(BUDGET)

select-models:
	docker compose exec worker limes select-models $(ARGS)

evaluate:
	docker compose exec worker limes evaluate $(ARGS)

migrate:
	@test -n "$(ONTOLOGY_VERSION)" || { echo "error: migrate requires ONTOLOGY_VERSION=<v>"; exit 2; }
	docker compose exec worker limes migrate --ontology-version $(ONTOLOGY_VERSION)

backup:
	docker compose exec worker limes backup

# The one-shot embedding backfill (§13.3, between bootstrap steps 6 and 7):
# stamp_missing_embeddings has no CLI command (D-56), so the target runs it
# through the composition root with the inference context, exactly as a
# command would. The stamp is idempotent and reports the count.
stamp-embeddings:
	docker compose exec worker python -c '\
from limes.config import load_settings; \
from limes.logging_setup import configure_logging; \
from limes.composition import build_run_context, embedder_for; \
from limes.graph.loader import stamp_missing_embeddings; \
settings = load_settings(); \
configure_logging(settings); \
ctx = build_run_context(settings, needs_inference=True); \
stamped = stamp_missing_embeddings(ctx.driver, embedder_for(settings, ctx.client)); \
print(f"stamp-embeddings: {stamped} entities stamped"); \
ctx.driver.close()'

# Desktop client (wp-01): host-side lint/test, no Docker involved.
.PHONY: desktop-lint desktop-test desktop-install desktop-run

desktop-lint:
	./venv/bin/ruff check desktop/src desktop/tests

desktop-test:
	./venv/bin/python -m pytest desktop/tests/unit desktop/tests/contract -q

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
