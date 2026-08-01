# src/limes/ontology/validator.py | v1.0.0 | introduced by WP-03
"""Assertion validation against the ontology per Technical Specification §8.2.

`validate_assertions` partitions rather than raising: valid assertions pass
through, invalid ones are returned with reasons. The loader (WP-07) and the
pipeline run (WP-27) call this before anything reaches the graph, so an
out-of-ontology assertion is rejected with a precise reason, never written.
"""

from __future__ import annotations

from limes.ontology.model import Ontology
from limes.types import Assertion, ValidationError

_REASON_UNKNOWN_RELATION = "UNKNOWN_RELATION"
_REASON_DOMAIN_VIOLATION = "DOMAIN_VIOLATION"
_REASON_RANGE_VIOLATION = "RANGE_VIOLATION"
_REASON_NON_TEMPORAL_VALID_TO = "NON_TEMPORAL_HAS_VALID_TO"


def validate_assertions(
    assertions: list[Assertion], ontology: Ontology
) -> tuple[list[Assertion], list[ValidationError]]:
    """Partition `assertions` into accepted and rejected.

    An assertion is rejected when: the relation does not exist; the subject
    type violates the relation's domain (after supertype resolution); the
    object type violates its range; or a non-temporal relation carries a
    `valid_to` (non-temporal relations never have `valid_to` set, Doc 2 §5.1).
    """
    accepted: list[Assertion] = []
    rejected: list[ValidationError] = []

    for index, assertion in enumerate(assertions):
        relation_spec = ontology.relation_types.get(assertion.relation)
        if relation_spec is None:
            rejected.append(
                ValidationError(
                    assertion_index=index,
                    reason=_REASON_UNKNOWN_RELATION,
                    detail={"relation": assertion.relation},
                )
            )
            continue

        subject_type = assertion.subject.type
        object_type = assertion.object.type
        if not ontology.permits(assertion.relation, subject_type, object_type):
            if subject_type not in relation_spec.domain:
                rejected.append(
                    ValidationError(
                        assertion_index=index,
                        reason=_REASON_DOMAIN_VIOLATION,
                        detail={
                            "relation": assertion.relation,
                            "subject_type": subject_type,
                            "declared_domain": relation_spec.domain,
                        },
                    )
                )
            else:
                rejected.append(
                    ValidationError(
                        assertion_index=index,
                        reason=_REASON_RANGE_VIOLATION,
                        detail={
                            "relation": assertion.relation,
                            "object_type": object_type,
                            "declared_range": relation_spec.range,
                        },
                    )
                )
            continue

        if not relation_spec.temporal and assertion.validity.valid_to is not None:
            rejected.append(
                ValidationError(
                    assertion_index=index,
                    reason=_REASON_NON_TEMPORAL_VALID_TO,
                    detail={"relation": assertion.relation},
                )
            )
            continue

        accepted.append(assertion)

    return accepted, rejected
