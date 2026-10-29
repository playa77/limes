"""Distinct regression boundaries: directional candidates, dependence and strict reviews."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from limes.news.developments import DevelopmentEvidence, MatchReview, ReviewView, suggest


def evidence(key, *, subject="a", object_="b", url=None, dependency=None):
    return DevelopmentEvidence(
        evidence_id=key,
        kind="claim",
        subject_id=subject,
        object_id=object_,
        subject_label=subject,
        object_label=object_,
        relation="SUPPLIES",
        properties={"report_url": url, "modality": "denied"},
        dependency_key=dependency,
    )


def test_candidates_do_not_reverse_direction_or_infer_independence():
    a, b, reverse = evidence("a"), evidence("b"), evidence("reverse", subject="b", object_="a")
    result = suggest([a, b, reverse], [])
    assert len(result) == 1
    assert result[0].decision == "unresolved" and result[0].independence == "unknown"
    assert result[0].assessment == "unassessed"


def test_known_report_dependence_survives_review_and_revision():
    a, b = evidence("a", url="https://report"), evidence("b", url="https://report")
    first = ReviewView(
        request_id=uuid4(),
        left="a",
        right="b",
        decision="same_event",
        assessment="supports",
        independence="independent",
        rationale="Legacy label",
        investigation_id="case",
        recorded_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    second = first.model_copy(
        update={
            "request_id": uuid4(),
            "decision": "different_event",
            "recorded_at": datetime(2026, 2, 1, tzinfo=UTC),
        }
    )
    result = suggest([a, b], [second, first])[0]
    assert result.decision == "different_event" and result.independence == "dependent"
    assert result.review_id == str(second.request_id)


@pytest.mark.parametrize(
    "changes",
    [
        {"right": "a"},
        {"rationale": "  "},
        {"decision": "completed_fact"},
        {"independence": "corroborated"},
    ],
)
def test_review_rejects_self_link_blank_rationale_and_untyped_truth(changes):
    payload = dict(
        request_id=uuid4(), left="a", right="b", decision="unresolved", rationale="Check"
    )
    with pytest.raises(ValidationError):
        MatchReview(**(payload | changes))


def test_archive_inspection_bounds_decompression_and_rejects_paths(tmp_path):
    from limes.archive.store import ArchiveStore

    archive = ArchiveStore(tmp_path)
    key = archive.put("test", b"x" * 100000, "text/plain")
    payload, truncated = archive.preview(key)
    assert payload == b"x" * 65536 and truncated
    with pytest.raises(ValueError):
        archive.preview("../../outside")


def test_read_only_archive_dependency_does_not_create_storage(tmp_path):
    from types import SimpleNamespace

    from limes.api.deps import get_archive

    root = tmp_path / "missing-archive"
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(archive_path=root)))
    )
    archive = get_archive(request)
    assert not root.exists()
    with pytest.raises(FileNotFoundError):
        archive.preview("a" * 64)
