# src/limes/graph/temporal.py | v1.0.0 | introduced by WP-04
"""Composable temporal query fragments per Technical Specification §5.7.

`as_of`, `as_believed`, and `currently` return Cypher fragments filtering on
the bitemporal properties every relationship carries. They are composable
string builders — the only place these fragments are written, so call sites
never concatenate Cypher themselves (Doc 2 §5.7). Consumed by the NL-to-Cypher
generator and the coverage service.
"""

from __future__ import annotations

from datetime import datetime


def _param(alias: str, name: str) -> str:
    """A parameter name derived from the alias; call sites pass values under
    the same name."""
    return f"{alias}_{name}"


def as_of(alias: str, instant: datetime) -> str:
    """A validity-time filter: the interval contains `instant`."""
    p = _param(alias, "valid_as_of")
    return f"{alias}.valid_from <= ${p} AND ({alias}.valid_to IS NULL OR {alias}.valid_to > ${p})"


def as_believed(alias: str, instant: datetime) -> str:
    """A belief-time filter: the system believed the fact at `instant`."""
    p = _param(alias, "believed_as_of")
    return (
        f"{alias}.recorded_at <= ${p} AND "
        f"({alias}.retracted_at IS NULL OR {alias}.retracted_at > ${p})"
    )


def currently(alias: str) -> str:
    """A current-validity filter: no `valid_to` set."""
    return f"{alias}.valid_to IS NULL"


def as_of_params(alias: str, instant: datetime) -> dict[str, datetime]:
    """Parameter values for `as_of`; the fragment and its params always
    travel together."""
    return {_param(alias, "valid_as_of"): instant}


def as_believed_params(alias: str, instant: datetime) -> dict[str, datetime]:
    """Parameter values for `as_believed`."""
    return {_param(alias, "believed_as_of"): instant}
