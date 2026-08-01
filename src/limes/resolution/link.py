# src/limes/resolution/link.py | v1.0.0 | introduced by WP-25
"""`:Mention` and `SAME_AS` management per Technical Specification §8.8.5
and §5.8.

Every extracted endpoint gets a `:Mention` node — including deterministic-key
hits — because without one an unlink has nothing to detach and an extracted
assertion has no traceable surface form. `mention_id` is deterministic over
(document, type, normalized surface, offsets), so re-extracting the same
document merges into the same node instead of accumulating duplicates; a
re-extraction that changes the surface or its position creates a new mention,
and WP-27 unlinks the old one.

`SAME_AS` is a scored link from the mention to the entity: `method`
("deterministic", "auto", "adjudicated"), `score`, `decision_at`, and the
nullable `retracted_at` that `unlink` sets. Re-linking after an unlink
re-activates the same relationship (clears `retracted_at`, updates the
scoring). No node is ever deleted or absorbed (DD-04, AC-19).

This module is the sole writer of `:Mention` and `SAME_AS` (§15.2). The mint
branch of resolution writes no `SAME_AS` at all: the minted entity node does
not exist until the loader materializes it, and creating the relationship
would create the node — the one write the resolver is forbidden.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

import structlog

from limes.graph.driver import GraphDriver
from limes.types import Mention

logger = structlog.get_logger(__name__)

_MENTION_MERGE = """
MERGE (m:Mention {mention_id: $mention_id})
ON CREATE SET m.surface = $surface,
              m.type = $type,
              m.document_id = $document_id,
              m.start = $start,
              m.end = $end
""".strip()

_LINK_MERGE = """
MATCH (m:Mention {mention_id: $mention_id}), (e:Entity {entity_id: $entity_id})
MERGE (m)-[r:SAME_AS]->(e)
ON CREATE SET r.method = $method, r.score = $score, r.decision_at = $decision_at
ON MATCH SET r.method = $method, r.score = $score, r.decision_at = $decision_at,
             r.retracted_at = null
""".strip()

_UNLINK = """
MATCH (m:Mention {mention_id: $mention_id})-[r:SAME_AS]->(e:Entity {entity_id: $entity_id})
WHERE r.retracted_at IS NULL
SET r.retracted_at = $at
RETURN count(r) AS retracted
""".strip()


def create_mention(
    driver: GraphDriver,
    mention: Mention,
    document_id: str,
    start: int,
    end: int,
) -> str:
    """Create (or merge) the `:Mention` node for one extracted endpoint and
    return its deterministic `mention_id`.

    The id is a digest over everything that distinguishes one occurrence of
    a surface from another — document, inferred type, normalized surface,
    and document offsets — so re-extraction is idempotent on mentions.
    """
    mention_id = _mention_id(document_id, mention.type, mention.surface, start, end)
    driver.write_batch(
        [
            (
                _MENTION_MERGE,
                {
                    "mention_id": mention_id,
                    "surface": mention.surface,
                    "type": mention.type,
                    "document_id": document_id,
                    "start": start,
                    "end": end,
                },
            )
        ]
    )
    return mention_id


def link(
    driver: GraphDriver,
    mention_id: str,
    entity_id: str,
    method: str,
    score: float,
    decision_at: datetime,
) -> None:
    """Create the scored `SAME_AS` from the mention to the entity, or update
    it when it already exists — re-linking after an unlink re-activates the
    relationship instead of accumulating a second one."""
    driver.write_batch(
        [
            (
                _LINK_MERGE,
                {
                    "mention_id": mention_id,
                    "entity_id": entity_id,
                    "method": method,
                    "score": score,
                    "decision_at": decision_at,
                },
            )
        ]
    )


def unlink(
    driver: GraphDriver,
    mention_id: str,
    entity_id: str,
    at: datetime,
) -> None:
    """Retract the `SAME_AS` between the mention and the entity by setting
    `retracted_at`. The relationship and both nodes remain (AC-19); the
    count retracted is logged, never silent.

    Runs through the driver's raw session — same seam as the loader's
    `retract` — because the statement writes while returning a count, which
    `GraphDriver.read` (read access mode) refuses and `write_batch`
    aggregates away.
    """
    with driver._driver.session(default_access_mode="WRITE") as session:
        with session.begin_transaction() as tx:
            result = tx.run(
                _UNLINK,
                mention_id=mention_id,
                entity_id=entity_id,
                at=at,
            )
            records = list(result)
    retracted = records[0]["retracted"] if records else 0
    logger.info(
        "same_as retracted",
        mention_id=mention_id,
        entity_id=entity_id,
        retracted=retracted,
    )


def _mention_id(document_id: str, type_name: str, surface: str, start: int, end: int) -> str:
    material = "|".join([document_id, type_name, surface.casefold(), str(start), str(end)])
    return f"mention:{hashlib.sha256(material.encode('utf-8')).hexdigest()[:32]}"
