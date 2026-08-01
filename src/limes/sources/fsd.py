# src/limes/sources/fsd.py | v1.0.0 | introduced by WP-13
"""EU FSD adapter per Technical Specification §8.5.2.

Loads the EU Financial Sanctions Database consolidated list into `Sanction`
entities with the three-way decomposition of Doc 1 §5.4: TARGETS
(Sanction → Person/Corporation), IMPOSED_BY (Sanction → IGO), and
ESTABLISHED_BY (Sanction → LegalAct) as separate assertions, each with its
own interval and provenance — a sanction's target, imposing authority, and
establishing instrument are three facts with three sources and three
validity intervals.

The consolidated list is the full current list, and there is no FSD delta
API: `fetch` ignores the window and always pulls the whole file.
`supports_incremental` stays True per the source table because re-runs are
cheap and idempotent: re-normalizing the same payload reproduces the same
assertion_ids, and the loader skips the duplicates (AC-05).

Identity choices, all load-bearing:

- Sanctions key on `("fsd_id", "<id>:<regime>")` — the same FSD id can
  recur under different regimes, and the roadmap fixes the regime as part
  of the identity: `fsd_id:123:EU`.
- Persons and corporations carry no deterministic key in the data, so their
  ids are name digests in typed namespaces (`person:...`,
  `corporation:...`).
- The imposing authority derives from the regime alone: "EU" → the
  European Union (Q458), "UN" → the United Nations (Q1065). Any other
  regime has no mapped authority; its IMPOSED_BY is skipped and counted.
- Legal acts are citations ("2014/145/EU"), not CELEX numbers. They still
  ride the ontology's `celex` identifying key, with the value prefixed
  `FSD:` so a citation can never collide with a genuine CELEX number
  emitted by EUR-Lex (WP-12) while the key stays on the identifying_keys
  list.
- The consolidated list carries no per-sanction publication date, so every
  assertion's `valid_from` is the fetch instant. A later re-run therefore
  produces new intervals rather than skipped duplicates — honest, because a
  full snapshot cannot know when an entry entered the list.

Not emitted on purpose: the person's nationality countries. The sanction
targets the person, not their country, and TARGETS is one edge per subject;
emitting `Sanction → Country` would claim a targeting semantics the source
does not state.

The endpoint requires a public token that rotates. `FSD_URL` is the single
place to refresh it; it could not be verified live from this host.
`fetch_bytes` retries connection errors, timeouts, 429, and 5xx — never
403 — so a rotated token surfaces as `SourceFetchError` on the first
attempt, which is the correct honest behavior.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import structlog
from lxml import etree  # type: ignore[import-untyped]

from limes.errors import SourceParseError
from limes.sources.base import (
    ONTOLOGY_VERSION,
    deterministic_assertion_id,
    fetch_bytes,
    hash_entity_id,
    key_entity_id,
    now_utc,
    payload_hash,
)
from limes.types import (
    Assertion,
    EntityEndpoint,
    NormalizedRecord,
    Provenance,
    RawRecord,
    Validity,
)

logger = structlog.get_logger(__name__)

# The consolidated list endpoint. The public token rotates; when a fetch
# starts failing with HTTP 403, refresh the token here and nowhere else.
FSD_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
    "?token=dG9rZW4tMjAxNw=="
)

# Regime → imposing IGO as (wikidata_qid, label). The list names only the
# regime, never the authority; these two mappings are the ones the
# ontology's IMPOSED_BY range (Country/IGO) supports.
_IMPOSING_IGO_BY_REGIME: dict[str, tuple[str, str]] = {
    "EU": ("Q458", "European Union"),
    "UN": ("Q1065", "United Nations"),
}

# FSD SubjectType values map onto exactly two ontology types; anything else
# has no representable target and is skipped and counted.
_SUBJECT_TYPES: dict[str, str] = {"P": "Person", "E": "Corporation"}


class FsdAdapter:
    """EU FSD — the consolidated list of financial sanctions."""

    source_id = "fsd"
    name = "EU FSD"
    kind = "structured"
    trust_rank = 1.00
    supports_backfill = True
    supports_incremental = True

    def fetch(self, since: datetime | None, until: datetime | None) -> Iterator[RawRecord]:
        """GET the consolidated list. The window is ignored: the endpoint
        serves the full current list and there is no FSD delta API, so every
        run is a full load.

        `fetch_bytes` retries connection errors, timeouts, 429, and 5xx; a
        403 (rotated public token) or other 4xx is a permanent miss and
        surfaces as `SourceFetchError` — refresh `FSD_URL` rather than
        retrying.
        """
        payload = fetch_bytes(FSD_URL)
        fetched_at = now_utc()
        logger.info(
            "fsd: payload fetched",
            bytes=len(payload),
            fetched_at=fetched_at.isoformat(),
        )
        yield RawRecord(
            payload=payload,
            content_type="application/xml",
            source_url=FSD_URL,
            fetched_at=fetched_at,
        )

    def normalize(self, record: RawRecord) -> NormalizedRecord:
        """Convert one consolidated list payload into the sanction assertion
        set. Pure: never touches the network."""
        try:
            root = etree.fromstring(record.payload)
        except (etree.XMLSyntaxError, ValueError) as exc:
            raise SourceParseError(f"fsd: payload is not parseable XML: {exc}") from exc
        container = root.find("Sanctions")
        if container is None:
            raise SourceParseError("fsd: payload has no <Sanctions> container")

        assertions: list[Assertion] = []
        counts = {
            "sanctions": 0,
            "skipped_subject_type": 0,
            "skipped_unnamed": 0,
            "skipped_regime": 0,
            "skipped_legal_basis": 0,
        }
        for element in container.findall("Sanction"):
            counts["sanctions"] += 1
            assertions.extend(_normalize_sanction(self, element, record, counts))

        logger.info(
            "fsd: consolidated list normalized",
            **counts,
            assertions=len(assertions),
            source_id=self.source_id,
        )
        return NormalizedRecord(
            content_hash=payload_hash(record.payload),
            kind="structured",
            assertions=assertions,
        )


def _normalize_sanction(
    adapter: FsdAdapter,
    element: etree._Element,
    record: RawRecord,
    counts: dict[str, int],
) -> list[Assertion]:
    """One <Sanction> element → up to three assertions (TARGETS, IMPOSED_BY,
    ESTABLISHED_BY). Skipped facets are counted by reason, never dropped."""
    fsd_id = _text(element, "Id")
    regime = _text(element, "Regime")
    if fsd_id is None or regime is None:
        counts["skipped_subject_type"] += 1
        logger.warning(
            "fsd: sanction without id or regime; skipped",
            fsd_id=fsd_id,
            regime=regime,
        )
        return []

    subject_type = _text(element, "SubjectType")
    subject_name = _primary_name(element)
    if subject_type is None or subject_type not in _SUBJECT_TYPES:
        counts["skipped_subject_type"] += 1
        logger.warning(
            "fsd: unknown SubjectType; sanction skipped",
            fsd_id=fsd_id,
            subject_type=subject_type,
        )
        return []
    if subject_name is None:
        counts["skipped_unnamed"] += 1
        logger.warning(
            "fsd: subject without a name; sanction skipped",
            fsd_id=fsd_id,
            subject_type=subject_type,
        )
        return []

    # The regime is part of the identity: the same FSD id can recur under
    # different regimes, and they are different sanctions.
    sanction_key = ("fsd_id", f"{fsd_id}:{regime}")
    sanction = EntityEndpoint(
        entity_id=key_entity_id(sanction_key),
        type="Sanction",
        label=subject_name,
        deterministic_key=sanction_key,
    )
    target_type = _SUBJECT_TYPES[subject_type]
    target = EntityEndpoint(
        entity_id=hash_entity_id(target_type.lower(), subject_name),
        type=target_type,
        label=subject_name,
    )

    # No per-sanction date exists in the consolidated list; validity starts
    # at the fetch instant (see module docstring).
    validity = Validity(valid_from=record.fetched_at, recorded_at=record.fetched_at)
    provenance = _provenance(adapter)

    assertions = [
        Assertion(
            assertion_id=deterministic_assertion_id(
                adapter.source_id,
                "TARGETS",
                sanction.entity_id,
                target.entity_id,
                record.fetched_at,
            ),
            subject=sanction,
            relation="TARGETS",
            object=target,
            validity=validity,
            provenance=provenance,
        )
    ]

    if regime in _IMPOSING_IGO_BY_REGIME:
        qid, label = _IMPOSING_IGO_BY_REGIME[regime]
        igo_key = ("wikidata_qid", qid)
        authority = EntityEndpoint(
            entity_id=key_entity_id(igo_key),
            type="IGO",
            label=label,
            deterministic_key=igo_key,
        )
        assertions.append(
            Assertion(
                assertion_id=deterministic_assertion_id(
                    adapter.source_id,
                    "IMPOSED_BY",
                    sanction.entity_id,
                    authority.entity_id,
                    record.fetched_at,
                ),
                subject=sanction,
                relation="IMPOSED_BY",
                object=authority,
                validity=validity,
                provenance=provenance,
            )
        )
    else:
        counts["skipped_regime"] += 1
        logger.warning(
            "fsd: regime has no imposing authority; IMPOSED_BY skipped",
            fsd_id=fsd_id,
            regime=regime,
        )

    citation = _first_legal_act(element)
    if citation is None:
        counts["skipped_legal_basis"] += 1
        logger.warning(
            "fsd: sanction has no LegalBasis/LegalAct; ESTABLISHED_BY skipped",
            fsd_id=fsd_id,
        )
    else:
        # The citation is not a CELEX number; the FSD: prefix keeps the
        # namespace honest so no EUR-Lex CELEX can collide with it.
        act_key = ("celex", f"FSD:{citation}")
        legal_act = EntityEndpoint(
            entity_id=key_entity_id(act_key),
            type="LegalAct",
            label=citation,
            deterministic_key=act_key,
        )
        assertions.append(
            Assertion(
                assertion_id=deterministic_assertion_id(
                    adapter.source_id,
                    "ESTABLISHED_BY",
                    sanction.entity_id,
                    legal_act.entity_id,
                    record.fetched_at,
                ),
                subject=sanction,
                relation="ESTABLISHED_BY",
                object=legal_act,
                # Non-temporal relation: valid_to stays None, or the
                # ontology validator rejects the assertion.
                validity=validity,
                provenance=provenance,
            )
        )

    return assertions


def _text(element: etree._Element, tag: str) -> str | None:
    """The trimmed text of the first direct child `tag`, or None when the
    child is absent or empty."""
    child = element.find(tag)
    if child is None:
        return None
    raw = child.text
    if raw is None:
        return None
    stripped = str(raw).strip()
    return stripped or None


def _primary_name(sanction: etree._Element) -> str | None:
    """The first non-empty WholeName across the NameAlias elements. FSD
    order is meaningful: the first alias is the primary name, later ones
    are alternatives."""
    for alias in sanction.findall("NameAlias"):
        raw = alias.findtext("WholeName")
        if raw is None:
            continue
        stripped = str(raw).strip()
        if stripped:
            return stripped
    return None


def _first_legal_act(sanction: etree._Element) -> str | None:
    """The first LegalAct citation inside any LegalBasis block. FSD legal
    acts arrive as regulation citations ("2014/145/EU"); the separate
    Regulation elements are duplicates of the same basis and ignored."""
    for basis in sanction.findall("LegalBasis"):
        raw = basis.findtext("LegalAct")
        if raw is None:
            continue
        stripped = str(raw).strip()
        if stripped:
            return stripped
    return None


def _provenance(adapter: FsdAdapter) -> Provenance:
    return Provenance(
        source_id=adapter.source_id,
        source_trust=adapter.trust_rank,
        confidence=1.0,
        ontology_version=ONTOLOGY_VERSION,
    )
