// src/api/client.ts
// The one HTTP seam between the web client and the LIMES API, reached through
// the launcher's `/api` proxy (which injects the session bearer token the
// browser never sees). One method per endpoint — the TS port of the retired
// `limes_desktop.api.client.ApiClient`. No view constructs a URL or request;
// everything flows through this class (NFR-DC-074: the client is replaceable
// against any conforming API implementation).
//
// Redirect ordering: the launcher proxy forwards with follow_redirects=False,
// re-dispatches same-origin hops itself (bounded) and refuses cross-origin
// hops with a 502 envelope — so the browser never sees a 3xx from `/api` and
// never follows one out of the origin.

import { ApiError, ApiUnreachable } from "./errors"
import type {
  CoverageReport,
  CostLedger,
  DevelopmentView,
  EnrichmentResponse,
  EntityDetail,
  GraphNeighbors,
  HealthInfo,
  IngestRun,
  NewsClaim,
  NewsInvestigation,
  JsonObject,
  OfficesResponse,
  OperationJob,
  QueryOutcome,
  QuerySurface,
  SavedQuery,
  SearchHit,
  SourceInfo,
} from "./types"
import {
  arr,
  costLedgerFromApi,
  coverageReportFromApi,
  diagnosisFromApi,
  developmentViewFromApi,
  enrichmentFromApi,
  entityDetailFromApi,
  graphNeighborsFromApi,
  graphResultFromApi,
  healthInfoFromApi,
  ingestRunFromApi,
  nlqOutcomeFromApi,
  newsClaimFromApi,
  newsInvestigationFromApi,
  obj,
  officesFromApi,
  operationJobFromApi,
  savedQueryFromApi,
  searchHitFromApi,
  sourceInfoFromApi,
} from "./types"

const TO_OBJECT_SENTINEL = "API returned an invalid JSON response"

export class ApiClient {
  constructor(private readonly fetchImpl: typeof fetch = fetch) {}

  // -- liveness -----------------------------------------------------------

  async health(): Promise<HealthInfo> {
    return healthInfoFromApi(obj(await this.get("/api/health")))
  }

  // -- ontology -----------------------------------------------------------

  async ontology(): Promise<JsonObject> {
    return obj(await this.get("/api/ontology"))
  }

  async ontologyVersions(): Promise<string[]> {
    const rows = await this.get("/api/ontology/versions")
    return (arr(rows) as JsonObject[]).map((row) => String(row.version))
  }

  async builderSchema(): Promise<JsonObject> {
    return obj(await this.get("/api/builder/schema"))
  }

  // -- queries: every outcome carries cypher/results/coverage/notes and the
  //    empty-result diagnosis when applicable (AC-22/23/26). ----------------

  private async queryOutcome(
    path: string,
    surface: QuerySurface,
    body: JsonObject,
  ): Promise<QueryOutcome> {
    const data = obj(await this.post(path, body))
    return {
      source: surface,
      cypher: String(data.cypher ?? ""),
      results: data.results != null ? graphResultFromApi(obj(data.results)) : null,
      coverage: data.coverage != null ? coverageReportFromApi(obj(data.coverage)) : null,
      diagnosis: data.diagnosis != null ? diagnosisFromApi(obj(data.diagnosis)) : null,
      notes: arr(data.notes ?? []).map(String),
      nlq: surface === "nl" ? nlqOutcomeFromApi(data) : null,
    }
  }

  queryCypher(cypher: string, params: JsonObject = {}): Promise<QueryOutcome> {
    return this.queryOutcome("/api/query/cypher", "cypher", { cypher, params })
  }

  queryBuilder(spec: JsonObject): Promise<QueryOutcome> {
    return this.queryOutcome("/api/query/builder", "builder", spec)
  }

  /** NLQ execution; the outcome's question/validation_errors/plan_rejection
   *  ride on `nlq` so every surface can display its own metadata. */
  queryNl(question: string): Promise<QueryOutcome> {
    return this.queryOutcome("/api/query/nl", "nl", { question })
  }

  // -- entities -----------------------------------------------------------

  entity(entityId: string): Promise<EntityDetail> {
    return this.get(`/api/entity/${encodeURIComponent(entityId)}`).then((d) =>
      entityDetailFromApi(obj(d)),
    )
  }

  enrichment(entityId: string, filters: Record<string, string> = {}): Promise<EnrichmentResponse> {
    return this.get(
      `/api/entity/${encodeURIComponent(entityId)}/enrichment?${qs(filters)}`,
    ).then((d) => enrichmentFromApi(obj(d)))
  }

  publicOffices(filters: Record<string, string> = {}): Promise<OfficesResponse> {
    return this.get(`/api/public-offices?${qs(filters)}`).then((d) => officesFromApi(obj(d)))
  }

  entityNeighbors(entityId: string, filters: Record<string, string> = {}): Promise<GraphNeighbors> {
    return this.get(
      `/api/entity/${encodeURIComponent(entityId)}/neighbors?${qs(filters)}`,
    ).then((d) => graphNeighborsFromApi(obj(d)))
  }

  // -- search & coverage --------------------------------------------------

  async search(query: string, kind: string | null = null, limit = 50): Promise<SearchHit[]> {
    const params: Record<string, string> = { q: query, limit: String(limit) }
    if (kind !== null) params.kind = kind
    const hits = await this.get(`/api/search?${qs(params)}`)
    return (arr(hits) as JsonObject[]).map(searchHitFromApi)
  }

  coverage(request: JsonObject): Promise<CoverageReport> {
    return this.post("/api/coverage", request).then((d) => coverageReportFromApi(obj(d)))
  }

  // -- saved queries (FR-DC-033) --------------------------------------------

  async savedQueries(): Promise<SavedQuery[]> {
    const rows = await this.get("/api/saved-queries")
    return (arr(rows) as JsonObject[]).map(savedQueryFromApi)
  }

  async saveQuery(name: string, surface: string, payload: JsonObject = {}): Promise<string> {
    const data = obj(
      await this.post("/api/saved-queries", {
        question: name,
        cypher: surface,
        result_count: 0,
        pinned: false,
        ...payload,
      }),
    )
    return String(data.saved_query_id)
  }

  async deleteSavedQuery(savedQueryId: string): Promise<void> {
    await this.delete(`/api/saved-queries/${encodeURIComponent(savedQueryId)}`)
  }

  // -- operational surfaces (FR-DC-050..052) ---------------------------------

  async sources(): Promise<SourceInfo[]> {
    const rows = await this.get("/api/sources")
    return (arr(rows) as JsonObject[]).map(sourceInfoFromApi)
  }

  costLedger(period: string | null = null): Promise<CostLedger> {
    const suffix = period === null ? "" : `?period=${encodeURIComponent(period)}`
    return this.get(`/api/cost/ledger${suffix}`).then((d) => costLedgerFromApi(obj(d)))
  }

  async ingestStatus(): Promise<IngestRun[]> {
    const rows = await this.get("/api/ingest/status")
    return (arr(rows) as JsonObject[]).map(ingestRunFromApi)
  }

  /** Only reachability with an operator credential proves capability:
   *  200 `{"backup": true, ...}` when the injected token is an operator
   *  credential; 403 otherwise (the desktop-side prerequisite contract). */
  async operationCapabilities(): Promise<Record<string, boolean> | null> {
    try {
      const data = obj(await this.get("/api/operations/capabilities"))
      return { backup: Boolean(data.backup), jobs: Boolean(data.jobs) }
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        return null
      }
      if (error instanceof ApiUnreachable) {
        throw error
      }
      return null
    }
  }

  submitBackup(requestId: string): Promise<OperationJob> {
    return this.post("/api/operations/jobs", {
      request_id: requestId,
      command: "backup",
    }).then((d) => operationJobFromApi(obj(d)))
  }

  async operationStatus(jobId: string): Promise<OperationJob> {
    return this.get(`/api/operations/jobs/${encodeURIComponent(jobId)}`).then((d) =>
      operationJobFromApi(obj(d)),
    )
  }

  // -- news / developments (DC-15 / DC-16 surfaces) --------------------------

  async newsInvestigations(): Promise<NewsInvestigation[]> {
    const rows = await this.get("/api/news/investigations")
    return (arr(rows) as JsonObject[]).map(newsInvestigationFromApi)
  }

  async trackNews(payload: JsonObject): Promise<JsonObject> {
    const id = String(payload.investigation_id ?? "")
    return obj(await this.put(`/api/news/investigations/${encodeURIComponent(id)}`, payload))
  }

  async replayNews(key: string): Promise<JsonObject> {
    return obj(await this.post(`/api/news/investigations/${encodeURIComponent(key)}/replay`, {}))
  }

  async newsClaims(filters: Record<string, string> = {}): Promise<NewsClaim[]> {
    const rows = await this.get(`/api/news/claims?${qs(filters)}`)
    return (arr(rows) as JsonObject[]).map(newsClaimFromApi)
  }

  async newsDocument(key: string): Promise<JsonObject> {
    return obj(await this.get(`/api/news/documents/${encodeURIComponent(key)}`))
  }

  async newsDevelopments(
    key: string,
    filters: Record<string, string> = {},
  ): Promise<DevelopmentView> {
    return this.get(
      `/api/news/investigations/${encodeURIComponent(key)}/developments?${qs(filters)}`,
    ).then((d) => developmentViewFromApi(obj(d)))
  }

  async reviewEventMatch(key: string, payload: JsonObject): Promise<JsonObject> {
    return obj(
      await this.post(
        `/api/news/investigations/${encodeURIComponent(key)}/event-match-reviews`,
        payload,
      ),
    )
  }

  /** The immutable evidence behind one assertion (AC-DC-8 navigation). */
  async assertionEvidence(assertionId: string): Promise<JsonObject> {
    return obj(await this.get(`/api/news/assertions/${encodeURIComponent(assertionId)}/evidence`))
  }

  // -- transport ------------------------------------------------------------

  private async get(path: string): Promise<unknown> {
    return this.requestJSON("GET", path)
  }

  private async delete(path: string): Promise<unknown> {
    return this.requestJSON("DELETE", path)
  }

  private async post(path: string, body: JsonObject): Promise<unknown> {
    return this.requestJSON("POST", path, body)
  }

  private async put(path: string, body: JsonObject): Promise<unknown> {
    return this.requestJSON("PUT", path, body)
  }

  private async requestJSON(method: string, path: string, body?: JsonObject): Promise<unknown> {
    let response: Response
    try {
      response = await this.fetchImpl(path, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    } catch {
      throw new ApiUnreachable("API transport unavailable")
    }
    if (!response.ok) throw await this.classify(response)
    try {
      return (await response.json()) as unknown
    } catch {
      throw new ApiError(502, TO_OBJECT_SENTINEL)
    }
  }

  private async classify(response: Response): Promise<ApiError> {
    const raw = await response.text()
    let payload: unknown = null
    try {
      payload = JSON.parse(raw)
    } catch {
      // Non-JSON body surfaces verbatim.
    }
    let detail: string = raw
    if (isRecord(payload)) {
      // §6 envelope: {"error": {"code", "message", ...}}; FastAPI's plain
      // `{"detail": "..."}`; otherwise the raw text.
      const error = payload.error
      if (isRecord(error) && typeof error.message === "string") detail = error.message
      else if (typeof payload.detail === "string") detail = payload.detail
    }
    return new ApiError(response.status, detail)
  }
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function qs(params: Record<string, string>): string {
  return new URLSearchParams(params).toString()
}
