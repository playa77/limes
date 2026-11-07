"""BE-56: source-owned DIP supersession; preserve nodes, IDs and archived history.

Rollback restores only this migration's retractions. New binaries/ontology are
required while 1.4.0 entities remain: restore a pre-migration backup to run an
older binary. No global party deletion or unrelated-source rewrite is allowed.
"""

import json
import re
from datetime import UTC, datetime

from limes.errors import GraphWriteError
from limes.graph.driver import GraphDriver

TO_VERSION = "1.4.0"
DATA_REPAIR = True


def upgrade(driver: GraphDriver) -> None:
    offices = driver.read(
        "MATCH ()-[r:HOLDS_OFFICE]->(o:Office) WHERE r.source_id='bundestag_dip' "
        "AND o.body_id='BT' RETURN DISTINCT o.entity_id AS id, o.label AS label, "
        "o.office_key AS key LIMIT 50001",
        {},
        30,
    )
    if len(offices) > 50000:
        raise GraphWriteError("DIP office migration exceeds bounded scope")
    changes = []
    for office in offices:
        match = re.search(r"Wahlperiode (\d+)\)", str(office["label"]))
        if not match:
            raise GraphWriteError("DIP office has no identifiable legislative period")
        key = json.dumps(["bt", "member", match[1], None], ensure_ascii=False)
        if office["key"] not in (None, key):
            raise GraphWriteError("DIP office compound key conflicts with legacy identity")
        changes.append(
            (
                "MATCH (o:Office {entity_id:$id}) "
                "FOREACH (_ IN CASE WHEN o.office_key IS NULL THEN [1] ELSE [] END | "
                "SET o.office_key=$key, o.scope='bt', o.term=$term, o.role='member', "
                "o.be56_added_office_key=true)",
                {"id": office["id"], "key": key, "term": match[1]},
            )
        )
    for offset in range(0, len(changes), 500):
        driver.write_batch(changes[offset : offset + 500])
    at = datetime.now(UTC)
    for _ in range(100):
        result = driver.write_batch(
            [
                (
                    "MATCH ()-[r]->() WHERE r.source_id='bundestag_dip' "
                    "AND type(r) IN ['MEMBER_OF','HOLDS_OFFICE','OFFICE_AT'] "
                    "AND coalesce(r.evidence_channel,'legacy') <> 'dip_term_evidence' "
                    "AND r.retracted_at IS NULL WITH r LIMIT 500 "
                    "SET r.retracted_at=$at, r.be56_superseded_at=$at",
                    {"at": at},
                )
            ]
        )
        if result.properties_set == 0:
            return
    raise GraphWriteError("DIP migration exceeded 50,000 assertions; resubmit explicitly")


def rollback(driver: GraphDriver) -> None:
    """Restore this supersession without changing any other source's history."""
    driver.write_batch(
        [
            (
                "MATCH (o:Office {be56_added_office_key:true}) SET o.office_key=null, "
                "o.scope=null, o.term=null, o.role=null, o.be56_added_office_key=null",
                {},
            )
        ]
    )
    driver.write_batch(
        [
            (
                "MATCH ()-[r]->() WHERE r.source_id='bundestag_dip' "
                "AND r.be56_superseded_at IS NOT NULL "
                "AND r.retracted_at=r.be56_superseded_at "
                "SET r.retracted_at=null, r.be56_superseded_at=null",
                {},
            )
        ]
    )
