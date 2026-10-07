# tests/unit/test_errors.py | v1.0.0 | introduced by WP-02
import pytest

from limes.errors import (
    ConfigurationError,
    CypherValidationFailed,
    EndpointUnidentified,
    ExtractionError,
    ExtractionSchemaError,
    GraphWriteError,
    LimesError,
    OntologyError,
    QueryPlanRejected,
    SourceFetchError,
    SourceParseError,
    ValidationRejected,
)


@pytest.mark.parametrize(
    "error_cls",
    [
        ConfigurationError,
        OntologyError,
        SourceFetchError,
        SourceParseError,
        ExtractionError,
        ExtractionSchemaError,
        ValidationRejected,
        EndpointUnidentified,
        GraphWriteError,
        CypherValidationFailed,
        QueryPlanRejected,
    ],
)
def test_all_errors_are_limes_errors(error_cls):
    assert issubclass(error_cls, LimesError)
    assert issubclass(error_cls, Exception)


def test_limes_error_is_an_exception():
    assert issubclass(LimesError, Exception)


def test_error_message_survives_raise():
    with pytest.raises(ConfigurationError, match="LIMES_NEO4J_URI"):
        raise ConfigurationError("missing required configuration: LIMES_NEO4J_URI")
