# src/limes/errors.py | v1.0.0 | introduced by WP-02
"""Error hierarchy per Technical Specification §11.

Every error the system raises derives from `LimesError`. The subclasses carry
the retry semantics the specification assigns: `ConfigurationError` and
`OntologyError` are fatal at startup, `SourceFetchError` and `ExtractionError`
are retryable, `SourceParseError` and `ExtractionSchemaError` are record-level
skips, and the remaining active classes
mark assertion-, transaction-, or request-level rejections. Nothing is ever
silently dropped; a skip is counted at the point it is caught.
"""


class LimesError(Exception):
    """Base class for every error the system raises."""


class ConfigurationError(LimesError):
    """Fatal at startup: a required key is absent or invalid (AC-01)."""


class OntologyError(LimesError):
    """Fatal at startup: the ontology artifact is missing, invalid, or older
    than the version stamped in the graph."""


class SourceFetchError(LimesError):
    """Retryable: a source could not be fetched, or a registry lookup named an
    unknown source (AC-38)."""


class SourceParseError(LimesError):
    """Record-level: a fetched payload could not be parsed. The record is
    counted and skipped, never silently dropped."""


class ExtractionError(LimesError):
    """Retryable: an extraction call failed at the transport or provider
    level."""


class ExtractionSchemaError(LimesError):
    """Record-level: extraction output failed schema validation. The
    assertion is counted and rejected with a reason."""


class BudgetExhausted(LimesError):
    """Run-level, clean termination: a paid call would breach the ceiling
    (AC-14). The run closes with remaining documents marked queued."""


class ValidationRejected(LimesError):
    """Assertion-level: an assertion failed ontology validation. It is
    counted, rejected with a reason, never written."""


class EndpointUnidentified(LimesError):
    """Assertion-level: an assertion endpoint lacks an `entity_id` (AC-10).
    Rejected as `ENDPOINT_UNIDENTIFIED`, counted, never written."""


class GraphWriteError(LimesError):
    """Transaction-level: a graph write failed; the transaction is rolled
    back. Never retried more than once."""


class CypherValidationFailed(LimesError):
    """Request-level (HTTP 400): operator-supplied or generated Cypher failed
    deterministic validation."""


class QueryPlanRejected(LimesError):
    """Request-level (HTTP 422): the query plan was rejected by the
    plan gate (cartesian product, unbounded or too-deep expansion, or row
    estimates above the configured ceiling)."""
