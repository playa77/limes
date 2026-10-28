# src/limes/graph/queries.py | v1.0.0 | introduced by WP-07
"""Cypher templates for the graph loader per Technical Specification §5.6.

Every template is parameterized except the label and relationship-type
segments, which Cypher cannot parameterize in the general case (Doc 2 §5.6).
Those segments are built exclusively from `Ontology.labels_for` (loader.py)
and from relation names validated against the ontology — never from source
data, which keeps ingested text out of the query text.
"""


def merge_entity(labels: list[str], key_prop: str | None = None) -> str:
    """MERGE one endpoint node by `entity_id`, applying the full label set
    (`[type, supertype..., Entity]`) from `Ontology.labels_for`.

    `ON CREATE` stamps label, aliases, `label_embedding` (the merge stamp of
    §5.6 — every entity creation passes through this choke point), ontology
    version, creation time, and the deterministic key property. `ON MATCH`
    only adds unseen aliases — an existing label, key, embedding, and
    original ontology version are never overwritten, so a lower-trust source
    cannot degrade an entity a higher-trust source established (Doc 2 §5.6
    step 1, AC-09). The embedding is a function of the stored label, which
    the merge never changes, so re-merges never touch it; nodes created
    before the stamp existed are filled by the one-shot backfill
    (`loader.stamp_missing_embeddings`), never by this statement.
    """
    label_segment = ":".join(labels)
    key_set = f",\n              n.{key_prop} = $key_value" if key_prop else ""
    return f"""
MERGE (n:{label_segment} {{entity_id: $entity_id}})
ON CREATE SET n.label = $label,
              n.aliases = $aliases,
              n.label_embedding = $label_embedding,
              n.ontology_version = $ontology_version,
              n.created_at = $created_at{key_set}
ON MATCH SET n.aliases =
    [a IN $aliases WHERE NOT a IN coalesce(n.aliases, [])] + coalesce(n.aliases, [])
""".strip()


MISSING_ENTITY_IDS = """
MATCH (n:Entity)
WHERE n.entity_id IN $ids
RETURN n.entity_id AS entity_id
""".strip()

MISSING_EMBEDDINGS_READ = """
MATCH (n:Entity)
WHERE n.label_embedding IS NULL AND n.label IS NOT NULL
RETURN n.entity_id AS entity_id, n.label AS label
LIMIT $batch_size
""".strip()

EMBEDDING_STAMP = """
MATCH (n:Entity {entity_id: $entity_id})
SET n.label_embedding = $label_embedding
""".strip()


def create_relationship(relation: str) -> str:
    """Idempotent relationship creation (Doc 2 §5.6 steps 3–4) in one
    statement. When a relationship with the same `assertion_id` already
    exists between the same endpoints, nothing is written. Returns
    `'written'` or `'skipped'` as `outcome`."""
    return f"""
MATCH (s:Entity {{entity_id: $subject_id}}), (o:Entity {{entity_id: $object_id}})
OPTIONAL MATCH (s)-[existing:{relation} {{assertion_id: $assertion_id}}]->(o)
FOREACH (x IN CASE WHEN existing IS NULL THEN [1] ELSE [] END |
    CREATE (s)-[r:{relation}]->(o)
    SET r = $props
)
RETURN CASE WHEN existing IS NULL THEN 'written' ELSE 'skipped' END AS outcome
""".strip()


def close_interval(relation: str) -> str:
    """Close superseded intervals of the same type between the same endpoints
    (Doc 2 §5.6 step 5). Only intervals from the same `source_id` with null
    `valid_to` and strictly earlier `valid_from` are touched; relationships
    from other sources are never modified (step 6). Returns the count of
    intervals closed."""
    return f"""
MATCH (s:Entity {{entity_id: $subject_id}})-[r:{relation}]->(o:Entity {{entity_id: $object_id}})
WHERE r.valid_to IS NULL
  AND r.source_id = $source_id
  AND coalesce(r.evidence_channel, 'legacy') = coalesce($evidence_channel, 'legacy')
  AND r.valid_from < $valid_from
SET r.valid_to = $valid_from
RETURN count(r) AS closed
""".strip()


POSTAL_CODE_MERGE = """
MERGE (p:PostalCode {country_code: $country_code, postal_code: $postal_code})
ON CREATE SET p.nuts_code = $nuts_code, p.source_id = $source_id, p.recorded_at = $recorded_at
ON MATCH SET p.nuts_code = $nuts_code, p.source_id = $source_id, p.recorded_at = $recorded_at
""".strip()


RETRACT_STATEMENT = """
MATCH (s)-[r]->(o)
WHERE r.assertion_id IN $assertion_ids AND r.retracted_at IS NULL
SET r.retracted_at = $at
RETURN count(r) AS retracted
""".strip()
