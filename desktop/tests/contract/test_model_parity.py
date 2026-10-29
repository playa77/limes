"""Contract: client model mirrors of src/limes/api/models.py. AC-DC-7."""

import dataclasses

import limes_desktop.api.models as dc_models

import limes.api.models as api_models
import limes.api.routers.cost as api_cost
import limes.api.routers.entity as api_entity
import limes.api.routers.ingest_status as api_ingest
import limes.api.routers.query as api_query
import limes.api.routers.saved_queries as api_saved
import limes.api.routers.search as api_search
import limes.api.routers.sources as api_sources
import limes.news.models as api_news
import limes.operations.models as api_operations

# Every mirrored model the client consumes, including nested ones
# (NlqOutcome -> GraphResult -> EntityRef/EdgeRef; EntityDetail -> EntityRef;
# BuilderSpec -> BuilderHop). Router view models are mirrored too, so a shape
# change anywhere on the API surface trips this test. Router view models are
# passed as classes; the core models by name for the parity message.
MIRRORED: list[tuple[type, str]] = [
    (api_news.NewsClaimView, "NewsClaim"),
    (api_news.Investigation, "NewsInvestigation"),
    (api_operations.Job, "OperationJob"),
    (api_operations.JobRequest, "OperationRequest"),
    (api_query.QueryResponse, "QueryOutcome"),
    (api_entity.NeighborResponse, "GraphNeighbors"),
    (api_models.EntityRef, "EntityRef"),
    (api_models.EdgeRef, "EdgeRef"),
    (api_models.GraphResult, "GraphResult"),
    (api_models.CoverageReport, "CoverageReport"),
    (api_models.Diagnosis, "Diagnosis"),
    (api_models.NlqOutcome, "NlqOutcome"),
    (api_models.BuilderHop, "BuilderHop"),
    (api_models.BuilderSpec, "BuilderSpec"),
    (api_search.SearchHit, "SearchHit"),
    (api_entity.NeighborRow, "NeighborRow"),
    (api_saved.SavedQueryView, "SavedQuery"),
    (api_sources.SourceView, "SourceInfo"),
    (api_cost.LedgerEntryView, "CostEntry"),
    (api_cost.LedgerView, "CostLedger"),
    (api_ingest.RunStatus, "IngestRun"),
]


def _api_fields(cls: type) -> set[str]:
    if hasattr(cls, "model_fields"):  # pydantic v2
        return set(cls.model_fields)
    return {f.name for f in dataclasses.fields(cls)}


def _client_fields(cls: type) -> set[str]:
    return {f.name for f in dataclasses.fields(cls)}


def test_field_parity() -> None:
    for api_model, dc_name in MIRRORED:
        dc_cls = getattr(dc_models, dc_name)
        assert _client_fields(dc_cls) == _api_fields(api_model), (
            f"{dc_name}: client mirror out of sync with limes.api.models — "
            f"update desktop/src/limes_desktop/api/models.py"
        )
