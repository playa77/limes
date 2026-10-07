# src/limes/cli/select_models.py | v1.0.0 | introduced by WP-29
"""Select and validate catalogue models, optionally measuring all four roles.

Provisional confirmation is opt-in. Complete measured selections record scores,
dataset identity, inference parameters and dated pins in separate non-secret files.
Nothing triggers data re-extraction; changes report their impact instead.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
import typer

from limes.cli.evaluate import (
    adjudication_accuracy,
    load_calibration_set,
    load_gold_set,
    load_reference_questions,
    macro_f1,
    measure_extraction,
    nl2cypher_evaluation,
    resolution_evaluation,
)
from limes.config_files import update_model_pins
from limes.errors import LimesError
from limes.logging_setup import configure_logging

logger = structlog.get_logger(__name__)

# Refresh point: the local configuration file the pins are written into —
# the same file `load_settings` reads (`env_file=".env"`).
ENV_FILE = Path("config/models.env")

# §8.7.2 role criteria: cost ceiling in USD per million tokens (blended:
# mean of prompt and completion price) and whether declared structured
# output is mandatory for the role. Language competence is not declarable
# in the catalogue — it is the operator's confirmation (stage 1) and the
# measured metrics (stage 2) that decide it.
ROLE_CRITERIA: dict[str, dict[str, Any]] = {
    "extraction": {"cost_ceiling_per_m_usd": 0.50, "require_structured_output": True},
    "adjudication": {"cost_ceiling_per_m_usd": 0.30, "require_structured_output": True},
    "embedding": {"cost_ceiling_per_m_usd": 0.20, "require_structured_output": False},
    "nl2cypher": {"cost_ceiling_per_m_usd": 1.00, "require_structured_output": False},
}

# The embedding dimension ceiling (§8.7.2) and the maximum number of
# candidates evaluated per role in the measured stage.
EMBEDDING_MAX_DIMENSIONS = 1536
MEASURED_CANDIDATES_PER_ROLE = 3

ROLE_ENV_KEYS = {
    "extraction": "LIMES_EXTRACTION_MODEL",
    "adjudication": "LIMES_ADJUDICATION_MODEL",
    "embedding": "LIMES_EMBEDDING_MODEL",
    "nl2cypher": "LIMES_NL2CYPHER_MODEL",
}


def select_models(
    provisional: bool = typer.Option(
        False, "--provisional", help="Stage 1: rank by criteria, pin after confirmation"
    ),
    measured: bool = typer.Option(
        False, "--measured", help="Stage 2: evaluate the top candidates, pin the winner"
    ),
    confirm: bool = typer.Option(False, "--confirm", help="Ask before each provisional pin"),
    budget: float | None = typer.Option(
        None,
        "--budget",
        min=0,
        help="Deprecated compatibility option; ignored",
    ),
) -> None:
    """Pin the model identifiers for the four roles (Doc 2 §8.7.2)."""
    if provisional == measured:
        raise LimesError("exactly one of --provisional or --measured is required")
    from limes.config import load_settings

    settings = load_settings()
    configure_logging(settings)
    from limes.composition import build_run_context

    ctx = build_run_context(
        settings,
        needs_inference=True,
        budget_eur=Decimal(str(budget)) if budget is not None else None,
    )
    try:
        if provisional:
            _provisional(ctx, confirm=(confirm is True))
        else:
            _measured(ctx)
    finally:
        ctx.driver.close()


def validate_pins(pins: dict[str, str], catalogue: list[dict[str, Any]]) -> None:
    """Refuse missing, typoed or retired identifiers before writing any pin."""
    available = {entry.get("id") for entry in catalogue}
    unknown = [f"{role}: {model}" for role, model in pins.items() if model not in available]
    if unknown:
        raise LimesError("models absent from current catalogue: " + ", ".join(unknown))


def filter_candidates(catalogue: list[dict[str, Any]], role: str) -> list[dict[str, Any]]:
    """The catalogue entries that satisfy the role's machine-verifiable
    §8.7.2 criteria, ranked by blended cost then by declared structured
    output. Models without declared pricing are excluded."""
    criteria = ROLE_CRITERIA[role]
    candidates: list[dict[str, Any]] = []
    for entry in catalogue:
        model_id = entry.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        pricing = entry.get("pricing") or {}
        if "prompt" not in pricing or "completion" not in pricing:
            continue
        try:
            prompt = float(pricing.get("prompt") or 0.0)
            completion = float(pricing.get("completion") or 0.0)
        except (TypeError, ValueError):
            continue
        blended_per_m = (prompt + completion) / 2 * 1e6
        if blended_per_m > criteria["cost_ceiling_per_m_usd"]:
            continue
        supported = entry.get("supported_parameters") or {}
        structured = (
            bool(supported.get("structured_outputs", False))
            if isinstance(supported, dict)
            else "structured_outputs" in supported or "response_format" in supported
        )
        if criteria["require_structured_output"] and not structured:
            continue
        architecture = entry.get("architecture") or {}
        dimensions = architecture.get("embedding_dimensions")
        if role == "embedding" and dimensions is not None:
            try:
                if int(dimensions) > EMBEDDING_MAX_DIMENSIONS:
                    continue
            except (TypeError, ValueError):
                pass
        candidates.append(
            {
                "id": str(model_id),
                "blended_per_m": round(blended_per_m, 6),
                "structured_outputs": structured,
                "description": str(entry.get("description") or "")[:120],
            }
        )
    return sorted(candidates, key=lambda c: (c["blended_per_m"], not c["structured_outputs"]))


def _provisional(ctx: Any, *, confirm: bool = False) -> None:
    """Stage 1: print and confirm the top candidate per role, write the
    pins. Never reads the gold set (AC-36)."""
    catalogue = ctx.client.catalogue()
    if not catalogue:
        raise LimesError("catalogue returned no models")
    pins: dict[str, str] = {}
    for role in ROLE_CRITERIA:
        candidates = filter_candidates(catalogue, role)
        if not candidates:
            typer.echo(f"select-models: no {role} candidate within the cost ceiling; skipped")
            continue
        top_three = candidates[:3]
        typer.echo(f"select-models: {role} candidates (ranked):")
        for index, candidate in enumerate(top_three, 1):
            typer.echo(
                f"  {index}. {candidate['id']}  ${candidate['blended_per_m']:.3f}/M blended"
                + ("  [structured output]" if candidate["structured_outputs"] else "")
            )
        if not confirm or _confirm(f"  Pin {top_three[0]['id']} for {role}? [y/N] "):
            pins[role] = str(top_three[0]["id"])
        else:
            typer.echo(f"  {role}: skipped by operator")
    if not pins:
        raise LimesError("no role pinned; nothing written")
    validate_pins(pins, catalogue)
    _write_pins(pins, "provisional")


def _measured(ctx: Any) -> None:
    """Stage 2: require a gold set ≥ 1.0.0, evaluate the top candidates
    per role with the WP-30 harness, write the winners, and report the
    impact of a model change without performing it (AC-37)."""

    gold_items = load_gold_set(ctx.settings.gold_set_path)
    version = _gold_set_version(gold_items)
    if _version_tuple(version) < (1, 0, 0):
        raise LimesError(
            f"measured stage requires a gold set at version >= 1.0.0; this set is {version}"
        )
    calibration = load_calibration_set(ctx.settings.gold_set_path.parent / "calibration_set.jsonl")
    questions = load_reference_questions(
        ctx.settings.ontology_path.parent.parent / "reference_questions" / "questions.yaml"
    )

    catalogue = ctx.client.catalogue()
    if not catalogue:
        raise LimesError("catalogue returned no models")
    winners: dict[str, str] = {}
    measurements: dict[str, dict[str, float]] = {}
    for role in ROLE_CRITERIA:
        candidates = filter_candidates(catalogue, role)[:MEASURED_CANDIDATES_PER_ROLE]
        if not candidates:
            typer.echo(f"select-models: no {role} candidate within the cost ceiling; skipped")
            continue
        scores = {
            str(candidate["id"]): _score_role(
                role, str(candidate["id"]), ctx, gold_items, calibration, questions
            )
            for candidate in candidates
        }
        if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores.values()):
            raise LimesError(f"invalid evaluation score for {role}; pins unchanged")
        measurements[role] = scores
        winner = max(scores, key=lambda model: scores[model])
        winners[role] = winner
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        typer.echo(
            f"select-models: {role}: "
            + ", ".join(f"{model} {score:.4f}" for model, score in ranked)
        )
    if not winners:
        raise LimesError("no role pinned; nothing written")
    if set(winners) != set(ROLE_ENV_KEYS):
        raise LimesError(
            "measured selection requires candidates for all four roles; pins unchanged"
        )
    validate_pins(winners, catalogue)
    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "gold_set_version": version,
        "gold_set_sha256": hashlib.sha256(ctx.settings.gold_set_path.read_bytes()).hexdigest(),
        "scores": measurements,
        "winners": winners,
        "inference_parameters": {
            "temperature": ctx.settings.inference_temperature,
            "max_tokens": ctx.settings.inference_max_tokens,
            "reasoning_effort": ctx.settings.inference_reasoning_effort,
        },
    }
    report_path = ENV_FILE.with_suffix(".evaluation.json")
    from limes.config_files import atomic_write_text

    atomic_write_text(report_path, json.dumps(report, indent=2) + "\n")
    _write_pins(winners, "measured")
    _report_affected(ctx, winners)


def _score_role(
    role: str,
    model_id: str,
    ctx: Any,
    gold_items: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    questions: list[dict[str, Any]],
) -> float:
    """The §8.7.2 selector metric for one candidate model. Extraction needs
    a per-candidate extractor — constructed by `composition.extractor_for`,
    the AC-40 surface; the other three roles take the model id directly."""
    from limes.composition import extractor_for

    if role == "extraction":
        candidate_settings = ctx.settings.model_copy(update={"extraction_model": model_id})
        extractor = extractor_for(candidate_settings, ctx.client)
        metrics = measure_extraction(extractor, gold_items, candidate_settings, ctx.ontology)
        return macro_f1(metrics, gold_items)
    if role == "adjudication":
        return adjudication_accuracy(ctx, calibration, model_id=model_id)
    if role == "embedding":
        scores = resolution_evaluation(ctx, calibration, embedding_model=model_id)
        return float(scores["recall@10"])
    if role == "nl2cypher":
        scores = nl2cypher_evaluation(ctx, questions, model_id=model_id)
        return float(scores["validation_pass_rate"])
    raise LimesError(f"unknown role: {role}")


def _report_affected(ctx: Any, winners: dict[str, str]) -> None:
    """Stage-2 impact report (AC-37): what a model change means, measured,
    never executed."""
    previous = ctx.settings
    if winners.get("extraction") != previous.extraction_model:
        documents = _count_cached_documents(ctx.driver, previous.extraction_model)
        sources = _count_extraction_sources(ctx.driver, previous.extraction_model)
        estimate = _reextraction_cost_estimate(ctx, documents, winners["extraction"])
        typer.echo(
            f"select-models: extraction model change: {previous.extraction_model or '(none)'} -> "
            f"{winners['extraction']}: {sources} sources, {documents} cached documents affected; "
            f"re-extraction cost estimate EUR {estimate:.4f}; no re-extraction performed"
        )
    if winners.get("embedding") != previous.embedding_model:
        entities = _count_entity_nodes(ctx.driver)
        typer.echo(
            f"select-models: embedding model change: {previous.embedding_model or '(none)'} -> "
            f"{winners['embedding']}: {entities} entity labels must be re-embedded; "
            "a vector index rebuild is required and was NOT executed"
        )


def _count_cached_documents(driver: Any, model_id: str) -> int:
    rows = driver.read(
        "MATCH (c:ExtractionCacheEntry) WHERE c.model_id = $model_id "
        "RETURN count(DISTINCT c.content_hash) AS c",
        {"model_id": model_id},
        60,
    )
    return int(rows[0]["c"])


def _count_extraction_sources(driver: Any, model_id: str) -> int:
    rows = driver.read(
        "MATCH ()-[r]->() WHERE r.extractor_model = $model_id "
        "RETURN count(DISTINCT r.source_id) AS c",
        {"model_id": model_id},
        60,
    )
    return int(rows[0]["c"])


def _count_entity_nodes(driver: Any) -> int:
    rows = driver.read("MATCH (e:Entity) RETURN count(e) AS c", {}, 60)
    return int(rows[0]["c"])


def _reextraction_cost_estimate(ctx: Any, documents: int, model_id: str) -> Decimal:
    """The re-extraction cost estimate: documents × the §9.3 measured token
    basis × the winner's blended price, in EUR. An overestimate is the safe
    direction for planning; the basis is documented."""
    from limes.cli.evaluate import TOKENS_PER_DOCUMENT

    blended = _blended_price(ctx.client.catalogue(), model_id)
    usd = documents * TOKENS_PER_DOCUMENT * blended / 1e6
    return Decimal(str(usd)) * Decimal(str(ctx.settings.usd_eur_rate))


def _blended_price(catalogue: list[dict[str, Any]], model_id: str) -> float:
    """The winner's blended per-million USD price from the catalogue, or
    the conservative fallback the client uses for unknown models (D-23)."""
    for entry in catalogue:
        if entry.get("id") != model_id:
            continue
        pricing = entry.get("pricing") or {}
        try:
            prompt = float(pricing.get("prompt") or 0.0)
            completion = float(pricing.get("completion") or 0.0)
            return (prompt + completion) / 2 * 1e6
        except (TypeError, ValueError):
            break
    return 0.50


def _write_pins(pins: dict[str, str], stage: str) -> None:
    """Publish validated role pins through the existing locked model-only writer.

    Reject malformed role/stage updates before constructing keys or touching the
    file, so failed selections leave the previous pins usable.
    """
    if not pins or not set(pins) <= set(ROLE_ENV_KEYS):
        raise LimesError("pin update contains no pins or unknown roles")
    if stage not in ("provisional", "measured"):
        raise LimesError("unknown model pin stage")
    if stage == "measured" and set(pins) != set(ROLE_ENV_KEYS):
        raise LimesError("measured pins require successful evaluation of all four roles")
    values = {ROLE_ENV_KEYS[role]: model for role, model in pins.items()}
    values["LIMES_MODEL_PIN_STAGE"] = stage
    values["LIMES_MODEL_PIN_DATE"] = datetime.now(UTC).date().isoformat()
    update_model_pins(ENV_FILE, values)
    typer.echo(
        f"select-models: {len(pins)} pins written to {ENV_FILE} with LIMES_MODEL_PIN_STAGE={stage}"
    )


def _confirm(prompt: str) -> bool:
    """The operator confirmation §8.7.2 requires; injectable for tests."""
    answer = input(prompt).strip().lower()
    return answer in ("y", "yes")


def _gold_set_version(items: list[dict[str, Any]]) -> str:
    versions = {str(item["gold_set_version"]) for item in items}
    if len(versions) != 1:
        raise LimesError(f"gold set carries mixed versions: {sorted(versions)}")
    return versions.pop()


def _version_tuple(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))  # type: ignore[return-value]
