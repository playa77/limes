"""Refresh tracked graph identity and relevance without treating graph presence as tracking."""

from __future__ import annotations

from limes.graph.driver import GraphDriver
from limes.news.models import TrackingRequest


def queries_for(driver: GraphDriver, request: TrackingRequest) -> list[str]:
    rows = driver.read(
        "MATCH (n:Entity) WHERE n.entity_id IN $ids "
        "RETURN n.entity_id AS id, n.label AS label, n.aliases AS aliases",
        {"ids": request.entity_ids},
        30,
    )
    if {str(row["id"]) for row in rows} != set(request.entity_ids):
        raise ValueError("one or more tracked entities no longer exist")
    targets: list[str] = []

    def names(label: object, aliases: object) -> str:
        values = [str(label or "")]
        if isinstance(aliases, list):
            values += [str(value) for value in aliases[:2]]
        # Quote literal entity names; never allow source-controlled search operators.
        return (
            "("
            + " OR ".join(
                '"' + v.replace('"', " ").replace("\\", " ")[:150] + '"'
                for v in dict.fromkeys(values)
                if v.strip()
            )
            + ")"
        )

    for row in rows:
        targets.append(names(row["label"], row.get("aliases")))
    relations = driver.read(
        "MATCH (s:Entity)-[r]->(o:Entity) WHERE r.assertion_id IN $ids "
        "RETURN r.assertion_id AS id, s.label AS subject, s.aliases AS subject_aliases, "
        "o.label AS object, o.aliases AS object_aliases, type(r) AS relation",
        {"ids": request.assertion_ids},
        30,
    )
    if {str(row["id"]) for row in relations} != set(request.assertion_ids):
        raise ValueError("one or more tracked relations no longer exist")
    for row in relations:
        # Both participants matter. Relation type stays part of tracking identity;
        # forcing ontology names into search would exclude natural-language reporting.
        targets.append(
            names(row["subject"], row.get("subject_aliases"))
            + " "
            + names(row["object"], row.get("object_aliases"))
        )
    if not targets:
        raise ValueError("an investigation needs at least one entity or relation")
    if len(targets) > 4:
        raise ValueError("at most four targets per investigation acquisition cycle")
    return targets
