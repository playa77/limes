# src/limes/config.py | v1.0.0 | introduced by WP-02
"""Application configuration, loaded from environment variables.

`Settings` carries one typed field per Technical Specification §4.2 key.
`load_settings()` validates at startup: a missing or empty required key is a
`ConfigurationError` naming the key (AC-01). There is deliberately no
module-level singleton: the composition root (WP-26) constructs settings once
per process and passes them explicitly.

The `NEO4J_*` keys in `.env.example` (heap, page cache, transaction limits)
configure the Neo4j server container itself, not this application, so they are
not fields of `Settings`; `extra="ignore"` keeps them out of the model.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from limes.errors import ConfigurationError

ModelPinStage = Literal["provisional", "measured"]


class Settings(BaseSettings):
    """One field per Technical Specification §4.2 `LIMES_*` key."""

    model_config = SettingsConfigDict(
        env_prefix="LIMES_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- Neo4j ----------
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "neo4j"

    # ---------- OpenRouter ----------
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    extraction_model: str = ""
    adjudication_model: str = ""
    embedding_model: str = ""
    nl2cypher_model: str = ""
    embedding_dimensions: int = 1024
    model_pin_stage: ModelPinStage = "provisional"
    model_pin_date: str | None = None

    # ---------- Versioned artifacts ----------
    ontology_path: Path
    feeds_config_path: Path
    gold_set_path: Path
    baseline_path: Path
    extraction_prompt_version: str = "1.0.0"
    adjudication_prompt_version: str = "1.0.0"
    nl2cypher_prompt_version: str = "1.0.0"
    extraction_schema_version: str = "1.0.0"

    # ---------- Budget ----------
    monthly_budget_eur: Decimal = Field(default=Decimal("10.00"))
    usd_eur_rate: float = 0.92
    budget_soft_stop_fraction: float = 0.95

    # ---------- Gate and extraction ----------
    gate_min_entity_mentions: int = 2
    gate_spacy_model_de: str = "de_core_news_md"
    gate_spacy_model_en: str = "en_core_web_md"
    extraction_max_passages_per_call: int = 8
    extraction_max_input_tokens: int = 6000
    extraction_passage_window_sentences: int = 3

    # ---------- Entity resolution (§8.8.3) ----------
    er_autolink_cosine: float = 0.93
    er_autolink_margin: float = 0.05
    er_adjudicate_cosine: float = 0.82
    er_candidate_limit: int = 10

    # ---------- Query planning (§8.10.4) ----------
    query_default_limit: int = 500
    query_max_limit: int = 5000
    query_max_varlength_hops: int = 4
    query_max_estimated_rows_operator: int = 5_000_000
    query_max_estimated_rows_total: int = 20_000_000
    query_timeout_seconds: int = 120

    # ---------- Ingestion ----------
    backfill_days_unstructured: int = 90
    archive_path: Path
    http_timeout_seconds: int = 60
    http_max_retries: int = 4

    # ---------- Service ----------
    api_base_url: str = "http://api:8000"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"


# Keys that must be present and non-empty at startup. Everything else has a
# default in §4.2 and fails startup only when empty is an invalid value there.
_REQUIRED_KEYS = (
    "neo4j_uri",
    "neo4j_user",
    "neo4j_password",
    "ontology_path",
    "feeds_config_path",
    "gold_set_path",
    "baseline_path",
    "archive_path",
)


def load_settings() -> Settings:
    """Load and validate configuration from the environment.

    Raises `ConfigurationError` naming the first missing or empty required
    key (AC-01). A `ValidationError` from Pydantic is translated into the same
    error type so startup failure is always a `ConfigurationError`.
    """
    try:
        settings = Settings()  # type: ignore[call-arg]  # populated from env vars
    except ValidationError as exc:
        missing = ", ".join(str(e["loc"][0]) for e in exc.errors())
        raise ConfigurationError(f"invalid configuration: {missing}") from exc

    empty = [key for key in _REQUIRED_KEYS if not getattr(settings, key)]
    if empty:
        raise ConfigurationError(f"missing required configuration: {', '.join(empty)}")

    if settings.model_pin_stage == "measured":
        model_fields = (
            "extraction_model",
            "adjudication_model",
            "embedding_model",
            "nl2cypher_model",
        )
        unpinned = [name for name in model_fields if not getattr(settings, name)]
        if unpinned:
            raise ConfigurationError(
                "model pin stage is 'measured' but no model is pinned for: " + ", ".join(unpinned)
            )

    return settings
