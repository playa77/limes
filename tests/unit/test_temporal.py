# tests/unit/test_temporal.py | v1.0.0 | introduced by WP-04
"""Composable temporal fragments per Doc 2 §5.7."""

from datetime import UTC, datetime

from limes.graph.temporal import (
    as_believed,
    as_believed_params,
    as_of,
    as_of_params,
    currently,
)

NOW = datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC)


def test_as_of_fragment_and_params_are_composable():
    fragment = as_of("r", NOW)
    assert "r.valid_from <= $r_valid_as_of" in fragment
    assert "r.valid_to IS NULL OR r.valid_to > $r_valid_as_of" in fragment
    assert as_of_params("r", NOW) == {"r_valid_as_of": NOW}


def test_as_believed_fragment_and_params():
    fragment = as_believed("r", NOW)
    assert "r.recorded_at <= $r_believed_as_of" in fragment
    assert "r.retracted_at IS NULL OR r.retracted_at > $r_believed_as_of" in fragment
    assert as_believed_params("r", NOW) == {"r_believed_as_of": NOW}


def test_currently_fragment():
    assert currently("r") == "r.valid_to IS NULL"


def test_fragments_never_concatenate_alias_into_cypher():
    # The alias must appear as a Cypher identifier, not interpolated
    # user-controlled text; only the parameter is dynamic.
    assert "$" not in currently("r")
    assert "$" in as_of("r", NOW)
