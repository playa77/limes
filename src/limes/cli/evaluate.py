# src/limes/cli/evaluate.py | v1.0.0 | introduced by WP-30
"""The `evaluate` command and evaluation harness (Doc 2 §8.14, §12.5–12.6,
§15.3 Trace 4; Doc 1 §9.5).

`make evaluate` measures extraction quality against the gold set: precision,
recall, and F1 per relation type, compared against `gold_set/baseline.json`
— the gate's sole source of truth — and exits non-zero when a per-relation
F1 regresses beyond 0.05 absolute. The human record is appended to
`gold_set/CHANGELOG.md`, and every item is materialized as a `:GoldSetItem`
node (§5.8 — this module is its sole writer). Match semantics per §12.5:
exact match on `(subject.surface_normalized, relation,
object.surface_normalized)`, normalization = casefold + whitespace
collapse, evidence span ignored.

`--resolution` measures entity resolution against the calibration set
(§8.8.3): recall@10 (does the other surface appear among the top-10
candidates of a mention of the entity) and decision accuracy (does the
top-1 candidate identity agree with the pair's label). `--nl2cypher`
measures NL-to-Cypher generation quality against the reference questions:
the generation prompt is inline here — the production prompt belongs to
WP-33 — and the provisional validation-pass rate uses the same structural
check the reference set itself passes (D-47): declared labels/relations
exist in the ontology, no write clauses. WP-33's parse-level validator
supersedes it.

The command is a measurement instrument, not a gating loop: it always runs
the selected mode to completion and reports, except that a regression
against the stored baseline exits non-zero (AC-31).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import structlog
import typer
import yaml  # type: ignore[import-untyped]
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from limes.config import Settings
from limes.errors import ConfigurationError, ExtractionError
from limes.extraction.base import Extractor
from limes.graph.driver import GraphDriver
from limes.logging_setup import configure_logging
from limes.ontology.model import Ontology
from limes.types import Passage

logger = structlog.get_logger(__name__)

# The gold set version these artifacts declare; the full 200-item set is
# built after the 90-day backfill under the provisional pin (§13.3 step 9).
GOLD_SET_VERSION = "1.0.0"

# The regression gate's threshold: a per-relation F1 below the baseline by
# more than this absolute amount fails the run (AC-31).
REGRESSION_THRESHOLD = 0.05

# Token basis for the re-extraction cost estimate (Doc 1 §9.3 measurement:
# one passage-level call runs ~1200 input and ~350 output tokens).
TOKENS_PER_DOCUMENT = 1200 + 350

_GOLD_SET_ITEM_MERGE = """
MERGE (g:GoldSetItem {item_id: $item_id})
SET g.language = $language,
    g.passage = $passage,
    g.expected_json = $expected_json,
    g.gold_set_version = $gold_set_version
"""

_NL2CYPHER_INSTRUCTION = """Write a single read-only Cypher query that answers the question.

Rules:
- Use only the entity types and relation types declared in the ontology below.
- The graph stores one node per entity; the node labels are the entity type names.
- Never use CREATE, MERGE, DELETE, SET, or any procedure call.
- End the query with a LIMIT clause.
- Return only the Cypher statement, no explanation.

{ontology}

Question: {question}"""

# Write-clause and side-effect keywords refused by the structural check.
_WRITE_TOKENS = frozenset(
    {
        "CREATE",
        "MERGE",
        "DELETE",
        "DETACH",
        "SET",
        "REMOVE",
        "LOAD",
        "CALL",
        "APOC",
        "DROP",
    }
)

_LABEL_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def evaluate(
    resolution: bool = typer.Option(
        False, "--resolution", help="Also measure entity resolution against the calibration set"
    ),
    nl2cypher: bool = typer.Option(
        False,
        "--nl2cypher",
        help="Also measure NL-to-Cypher generation against the reference questions",
    ),
    budget: float | None = typer.Option(
        None,
        "--budget",
        min=0,
        help="The EUR envelope; without it, evaluation draws on the monthly ceiling",
    ),
) -> None:
    """Measure extraction quality (default), entity resolution
    (`--resolution`), or NL-to-Cypher generation (`--nl2cypher`), and gate
    the extraction baseline (AC-31)."""
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
        if not (resolution or nl2cypher):
            _evaluate_extraction(ctx)
        if resolution:
            _evaluate_resolution(ctx)
        if nl2cypher:
            _evaluate_nl2cypher(ctx)
    finally:
        ctx.driver.close()


# --------------------------------------------------------------------------
# Gold set
# --------------------------------------------------------------------------


def load_gold_set(path: Path) -> list[dict[str, Any]]:
    """Load and schema-validate `gold_set.jsonl` (one item per line). A
    missing, empty, or invalid file is a `ConfigurationError`: the gate must
    never run against a silently degraded corpus."""
    if not path.is_file():
        raise ConfigurationError(f"gold set missing: {path}")
    schema = _load_schema(path.parent / "gold_set.schema.json")
    items: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"gold set line {lineno} is not JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise ConfigurationError(f"gold set line {lineno} is not an object")
        error = next(iter(Draft202012Validator(schema).iter_errors(item)), None)
        if error is not None:
            raise ConfigurationError(f"gold set line {lineno} fails schema: {error.message}")
        items.append(item)
    if not items:
        raise ConfigurationError(f"gold set is empty: {path}")
    return items


def load_calibration_set(path: Path) -> list[dict[str, Any]]:
    """Load the calibration set: 100 hand-labeled entity-resolution pairs
    (§8.8.3). The shape is this module's contract (the spec fixes the
    counts, not the file format); a malformed line fails loudly."""
    if not path.is_file():
        raise ConfigurationError(f"calibration set missing: {path}")
    items: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"calibration line {lineno} is not JSON: {exc}") from exc
        required = {"item_id", "language", "type", "mention_a", "mention_b", "is_match", "kind"}
        if not isinstance(item, dict) or not required.issubset(item):
            raise ConfigurationError(
                f"calibration line {lineno} misses required fields: {sorted(required - set(item))}"
            )
        items.append(item)
    return items


def load_reference_questions(path: Path) -> list[dict[str, Any]]:
    """Load `reference_questions/questions.yaml` — five operator questions
    with hand-written reference Cypher (Doc 2 §12.6). The top level is the
    question list; each entry carries `question` and `reference_cypher`."""
    if not path.is_file():
        raise ConfigurationError(f"reference questions missing: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"reference questions unreadable: {path}: {exc}") from exc
    if not isinstance(data, list):
        raise ConfigurationError(f"reference questions has no question list: {path}")
    for entry in data:
        is_question = (
            isinstance(entry, dict) and "question" in entry and "reference_cypher" in entry
        )
        if not is_question:
            raise ConfigurationError(
                f"reference question entry misses question/reference_cypher: {entry}"
            )
    return data


def _load_schema(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError(f"gold set schema missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"gold set schema unreadable: {path}: {exc}") from exc
    assert isinstance(raw, dict)
    return raw


def _gold_set_version(items: list[dict[str, Any]]) -> str:
    """The single declared version across the items; a mixed set is a
    defect."""
    versions = {str(item["gold_set_version"]) for item in items}
    if len(versions) != 1:
        raise ConfigurationError(f"gold set carries mixed versions: {sorted(versions)}")
    return versions.pop()


# --------------------------------------------------------------------------
# Extraction measurement
# --------------------------------------------------------------------------


def measure_extraction(
    extractor: Extractor,
    items: list[dict[str, Any]],
    settings: Settings,
    ontology: Ontology,
) -> dict[str, dict[str, float]]:
    """Run the extractor over the gold set and return per-relation
    `{precision, recall, f1}` metrics.

    Multiset semantics: an expected tuple is consumed by one matching
    extracted tuple, so a duplicated extraction of the same fact counts one
    true positive and one false positive. Comparison is on normalized
    surfaces — casefold plus whitespace collapse (§12.5) — and the evidence
    span is ignored for matching.
    """
    expected: dict[str, Counter[tuple[str, str, str]]] = {}
    for item in items:
        for assertion in item["expected_json"]:
            relation = str(assertion["relation"])
            expected.setdefault(relation, Counter()).update(
                [
                    (
                        _normalize_surface(str(assertion["subject"]["surface"])),
                        relation,
                        _normalize_surface(str(assertion["object"]["surface"])),
                    )
                ]
            )

    extracted: dict[str, Counter[tuple[str, str, str]]] = {}
    rejected = 0
    for item in items:
        passage_text = str(item["passage"])
        result = extractor.extract(
            [Passage(index=0, text=passage_text, doc_start=0, doc_end=len(passage_text))],
            ontology,
            settings.extraction_prompt_version,
            settings.extraction_schema_version,
        )
        rejected += len(result.parse_errors)
        for assertion in result.assertions:
            relation = assertion.relation
            extracted.setdefault(relation, Counter()).update(
                [
                    (
                        _normalize_surface(assertion.subject.surface),
                        relation,
                        _normalize_surface(assertion.object.surface),
                    )
                ]
            )
        logger.info(
            "gold set item evaluated",
            item_id=item["item_id"],
            assertions=len(result.assertions),
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
        )
    if rejected:
        logger.warning("gold set evaluation rejected extraction items", count=rejected)

    metrics: dict[str, dict[str, float]] = {}
    for relation in sorted(set(expected) | set(extracted)):
        exp = expected.get(relation, Counter())
        ext = extracted.get(relation, Counter())
        true_positive = sum((ext & exp).values())
        false_positive = sum(ext.values()) - true_positive
        false_negative = sum(exp.values()) - true_positive
        positives = true_positive + false_positive
        relevant = true_positive + false_negative
        precision = true_positive / positives if positives else 0.0
        recall = true_positive / relevant if relevant else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics[relation] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
    return metrics


def macro_f1(metrics: dict[str, dict[str, float]], items: list[dict[str, Any]]) -> float:
    """The role score for model selection: the mean F1 over the relations
    the gold set covers — a relation the corpus never asks about cannot
    distinguish candidates."""
    covered = {str(a["relation"]) for item in items for a in item["expected_json"]}
    values = [metrics[r]["f1"] for r in sorted(covered) if r in metrics]
    return sum(values) / len(values) if values else 0.0


def _normalize_surface(surface: str) -> str:
    """The §12.5 match normalization: casefold plus whitespace collapse."""
    return " ".join(surface.casefold().split())


# --------------------------------------------------------------------------
# Resolution measurement
# --------------------------------------------------------------------------


def resolution_evaluation(
    ctx: Any,
    items: list[dict[str, Any]],
    *,
    embedding_model: str | None = None,
) -> dict[str, float]:
    """recall@10 and decision accuracy over the calibration set (§8.8.3).

    recall@10: for each true-match pair, does the other mention's
    normalized surface appear among the top-10 candidates of a mention of
    the entity? One direction is measured deliberately — the exact-label
    self-match of the entity's own mention would always satisfy the reverse
    direction and prove nothing.

    Accuracy: does the top-1 candidate identity agree with the pair's
    label? A match pair predicts match when either mention's top candidate
    carries the other's normalized surface; a non-match pair predicts
    non-match when neither does. The measurement is embedding-only — the
    adjudication band is the adjudicator's job, measured separately by
    `adjudication_accuracy`.
    """
    from limes.resolution import blocking

    model = embedding_model or ctx.settings.embedding_model
    recall_hits = 0
    true_pairs = 0
    correct = 0
    for item in items:
        vector_a = blocking.embed(
            [str(item["mention_a"])], ctx.client, model, ctx.settings.embedding_dimensions
        )[0]
        vector_b = blocking.embed(
            [str(item["mention_b"])], ctx.client, model, ctx.settings.embedding_dimensions
        )[0]
        candidates_a = blocking.candidates(ctx.driver, vector_a, str(item["type"]), 10)
        candidates_b = blocking.candidates(ctx.driver, vector_b, str(item["type"]), 10)
        labels_a = [_normalize_surface(str(c["label"])) for c in candidates_a]
        labels_b = [_normalize_surface(str(c["label"])) for c in candidates_b]

        if item["is_match"]:
            true_pairs += 1
            if _normalize_surface(str(item["mention_b"])) in labels_a:
                recall_hits += 1

        top_a = labels_a[0] if labels_a else None
        top_b = labels_b[0] if labels_b else None
        predicts_match = top_a == _normalize_surface(
            str(item["mention_b"])
        ) or top_b == _normalize_surface(str(item["mention_a"]))
        if predicts_match == item["is_match"]:
            correct += 1
        logger.info(
            "calibration pair evaluated",
            item_id=item["item_id"],
            predicts_match=predicts_match,
            is_match=item["is_match"],
            candidates_a=len(candidates_a),
            candidates_b=len(candidates_b),
        )
    recall = recall_hits / true_pairs if true_pairs else 0.0
    accuracy = correct / len(items) if items else 0.0
    return {"recall@10": round(recall, 4), "accuracy": round(accuracy, 4)}


def adjudication_accuracy(
    ctx: Any,
    items: list[dict[str, Any]],
    *,
    model_id: str,
) -> float:
    """Calibration-set accuracy of one adjudication model: for each pair,
    the pairwise adjudicator (D-32's pairwise prompt) decides same/not-same
    against the other mention as its top candidate. The candidate dict is
    a harness artifact — its `entity_id` is only a yes/no signal; the
    adjudicator never sees the graph."""
    from limes.resolution.adjudicate import adjudicate
    from limes.types import Mention

    correct = 0
    for item in items:
        mention = Mention(surface=str(item["mention_a"]), type=str(item["type"]))
        candidate: dict[str, str | float] = {
            "entity_id": f"calibration:{item['item_id']}",
            "label": str(item["mention_b"]),
            "score": 0.90,
        }
        entity_id, _ = adjudicate(
            mention,
            [candidate],
            ctx.client,
            ctx.settings.adjudication_prompt_version,
            model_id,
        )
        predicts_match = entity_id is not None
        if predicts_match == item["is_match"]:
            correct += 1
    return round(correct / len(items), 4) if items else 0.0


# --------------------------------------------------------------------------
# NL-to-Cypher measurement
# --------------------------------------------------------------------------


def nl2cypher_evaluation(
    ctx: Any,
    questions: list[dict[str, Any]],
    *,
    model_id: str | None = None,
) -> dict[str, float]:
    """Generation quality over the reference questions: the fraction of
    generated queries passing the structural check (the provisional
    validation-pass rate, D-47 — WP-33's parse-level validator supersedes
    it) and the mean token-agreement with the reference Cypher. The
    generation prompt is inline: the production prompt is WP-33's artifact.
    A question whose generation call fails is counted as failed, logged,
    and skipped — a measurement run must not abort on one bad call."""
    model = model_id or ctx.settings.nl2cypher_model
    if not model:
        raise ExtractionError("no nl2cypher model pinned; run select-models first")
    ontology_serialized = ctx.ontology.serialize_for_prompt()
    passed = 0
    agreement_total = 0.0
    for question in questions:
        prompt = _NL2CYPHER_INSTRUCTION.format(
            ontology=ontology_serialized, question=question["question"]
        )
        try:
            raw, _, _ = ctx.client.complete(
                [{"role": "system", "content": prompt}],
                model,
                "nl2cypher",
            )
        except ExtractionError as exc:
            logger.warning(
                "nl2cypher generation failed for question",
                question_id=question.get("id"),
                error=str(exc),
            )
            continue
        cypher = _strip_code_fence(raw)
        problems = structural_problems(cypher, ctx.ontology)
        if not problems:
            passed += 1
        else:
            logger.info(
                "generated cypher failed structural check",
                question_id=question.get("id"),
                problems=problems,
            )
        agreement_total += _token_agreement(cypher, str(question["reference_cypher"]))
    total = len(questions)
    return {
        "validation_pass_rate": round(passed / total, 4) if total else 0.0,
        "structural_agreement": round(agreement_total / total, 4) if total else 0.0,
    }


def structural_problems(cypher: str, ontology: Ontology) -> list[str]:
    """The structural reference check (D-47): every `:Name` in the Cypher
    must be a declared ontology entity or relation type, and no write or
    side-effect token may appear. Token-based on purpose — the check runs
    against the trusted reference set and as the provisional gate for
    generated Cypher; WP-33's parse-level validator is the production one.

    `SET` is refused as a bare token, so `OFFSET` is not caught — the
    tokenization makes false positives impossible for the writes that
    matter. `CALL` and `APOC` are refused wholesale: the read-only
    procedure allowlist is empty today (§7.2)."""
    problems: list[str] = []
    upper_tokens = _TOKEN_RE.findall(cypher.upper())
    for token in _WRITE_TOKENS:
        if token in upper_tokens:
            problems.append(f"WRITE_CLAUSE:{token}")
    known = set(ontology.entity_types) | set(ontology.relation_types) | set(ontology.supertypes)
    for name in _LABEL_RE.findall(cypher):
        if name not in known:
            problems.append(f"UNKNOWN_NAME:{name}")
    return problems


def _token_agreement(a: str, b: str) -> float:
    """Structural agreement as Jaccard similarity over normalized tokens —
    the fraction of tokens the two queries share. Token-level by design:
    agreement is a generation-quality signal, not a parse."""
    tokens_a = set(_TOKEN_RE.findall(a.upper()))
    tokens_b = set(_TOKEN_RE.findall(b.upper()))
    union = tokens_a | tokens_b
    if not union:
        return 1.0
    return len(tokens_a & tokens_b) / len(union)


def _strip_code_fence(raw: str) -> str:
    """Strip a markdown code fence if the model wrapped the Cypher in one."""
    match = re.match(r"^```(?:cypher)?\s*(.*?)\s*```$", raw.strip(), re.S)
    return match.group(1) if match else raw.strip()


# --------------------------------------------------------------------------
# Baseline and durability
# --------------------------------------------------------------------------


def read_baseline(path: Path) -> dict[str, Any]:
    """The stored baseline, or an empty dict on a first run — the first
    evaluation establishes the baseline and never regresses (AC-31)."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"baseline unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"baseline is not an object: {path}")
    return data


def write_baseline(
    path: Path,
    metrics: dict[str, dict[str, float]],
    gold_set_version: str,
) -> None:
    """Write the machine-readable baseline — the regression gate's sole
    source of truth (§12.5)."""
    payload = {
        "gold_set_version": gold_set_version,
        "run_at": datetime.now(UTC).isoformat(),
        "per_relation": metrics,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def regressed_relations(
    baseline: dict[str, Any], metrics: dict[str, dict[str, float]]
) -> list[str]:
    """The relations whose new F1 sits more than 0.05 below the baseline —
    the AC-31 gate. Relations absent from the baseline do not regress."""
    stored = baseline.get("per_relation", {})
    if not isinstance(stored, dict):
        raise ConfigurationError("baseline per_relation is not an object")
    regressed: list[str] = []
    for relation, values in metrics.items():
        previous = stored.get(relation)
        if not isinstance(previous, dict) or "f1" not in previous:
            continue
        if values["f1"] < float(previous["f1"]) - REGRESSION_THRESHOLD:
            regressed.append(relation)
    return regressed


def write_gold_set_items(driver: GraphDriver, items: list[dict[str, Any]]) -> None:
    """Materialize the gold set as `:GoldSetItem` nodes — the §5.8 durable
    record of the evaluation corpus; this module is its sole writer."""
    statements = [
        (
            _GOLD_SET_ITEM_MERGE,
            {
                "item_id": str(item["item_id"]),
                "language": str(item["language"]),
                "passage": str(item["passage"]),
                "expected_json": json.dumps(item["expected_json"], sort_keys=True),
                "gold_set_version": str(item["gold_set_version"]),
            },
        )
        for item in items
    ]
    driver.write_batch(statements)


# --------------------------------------------------------------------------
# Command bodies
# --------------------------------------------------------------------------


def _evaluate_extraction(ctx: Any) -> None:
    """Trace 4: extract over the gold set, compute per-relation metrics,
    write the baseline and the human record, gate the regression, and
    materialize the `:GoldSetItem` nodes."""
    settings = ctx.settings
    items = load_gold_set(settings.gold_set_path)
    assert ctx.extractor is not None
    metrics = measure_extraction(ctx.extractor, items, settings, ctx.ontology)
    for relation, values in sorted(metrics.items()):
        typer.echo(
            f"evaluate: {relation}: precision {values['precision']:.4f}, "
            f"recall {values['recall']:.4f}, f1 {values['f1']:.4f}"
        )
    write_gold_set_items(ctx.driver, items)

    baseline = read_baseline(settings.baseline_path)
    version = _gold_set_version(items)
    if not baseline:
        write_baseline(settings.baseline_path, metrics, version)
        typer.echo(f"evaluate: baseline recorded ({len(metrics)} relations)")
    else:
        write_baseline(settings.baseline_path, metrics, version)
        regressed = regressed_relations(baseline, metrics)
        if regressed:
            for relation in regressed:
                previous = float(baseline["per_relation"][relation]["f1"])
                typer.echo(
                    f"evaluate: REGRESSION: {relation} f1 {metrics[relation]['f1']:.4f} "
                    f"vs baseline {previous:.4f}"
                )
            _append_changelog(settings, metrics, regressed)
            raise typer.Exit(1)
        typer.echo("evaluate: no regression beyond 0.05; baseline updated")
    _append_changelog(settings, metrics, regressed=[])


def _append_changelog(
    settings: Settings,
    metrics: dict[str, dict[str, float]],
    regressed: list[str],
) -> None:
    """The human-readable record in `gold_set/CHANGELOG.md` (§12.5)."""
    path = settings.gold_set_path.parent / "CHANGELOG.md"
    lines = [
        "",
        f"## {datetime.now(UTC).date().isoformat()} — evaluation run",
        f"- {len(metrics)} relation types measured; "
        + ("; ".join(f"{r} f1={metrics[r]['f1']:.4f}" for r in sorted(metrics))),
    ]
    if regressed:
        lines.append(f"- REGRESSED vs baseline: {', '.join(regressed)}")
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _evaluate_resolution(ctx: Any) -> None:
    calibration = load_calibration_set(ctx.settings.gold_set_path.parent / "calibration_set.jsonl")
    scores = resolution_evaluation(ctx, calibration)
    typer.echo(
        f"evaluate --resolution: recall@10 {scores['recall@10']:.4f}, "
        f"accuracy {scores['accuracy']:.4f}"
    )


def _evaluate_nl2cypher(ctx: Any) -> None:
    # The reference questions live beside the ontology artifact: derived
    # from the configured path so both dev and container layouts resolve
    # (there is no dedicated config key; the questions are a repo fixture).
    questions_path = (
        ctx.settings.ontology_path.parent.parent / "reference_questions" / "questions.yaml"
    )
    questions = load_reference_questions(questions_path)
    scores = nl2cypher_evaluation(ctx, questions)
    typer.echo(
        f"evaluate --nl2cypher: validation-pass rate {scores['validation_pass_rate']:.4f}, "
        f"structural agreement {scores['structural_agreement']:.4f}"
    )
