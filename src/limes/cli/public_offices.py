"""Explicit bounded operator reviews; never infer identity from a name."""

from typing import Annotated

import typer
from pydantic import TypeAdapter, ValidationError

from limes.config import load_settings
from limes.errors import LimesError
from limes.graph.loader import review_person_identity
from limes.public_offices.models import IdentityReview


def identify(
    identity_reviews: Annotated[str, typer.Option("--identity-reviews")],
) -> None:
    try:
        reviews = TypeAdapter(list[IdentityReview]).validate_json(identity_reviews)
    except ValidationError as exc:
        raise LimesError("invalid identity review JSON") from exc
    if not 1 <= len(reviews) <= 100:
        raise LimesError("select one to 100 explicit identity reviews")
    from limes.composition import build_run_context

    ctx = build_run_context(load_settings(), needs_inference=False)
    try:
        for review in reviews:
            if not ctx.archive.exists(review.evidence_hash):
                raise LimesError("identity review evidence must already exist in the archive")
        for review in reviews:
            review_person_identity(ctx.driver, review)
        typer.echo(f"public office identity reviews recorded: {len(reviews)}")
    finally:
        ctx.driver.close()
