// src/api/types.ts
// Client-side mirrors of the API response models (src/limes/api/models.py and
// the router view models). These are the TS ports of the retired
// `limes_desktop.api.models` dataclasses; end-to-end parity with the live API
// is pinned by `desktop/tests/contract/test_openapi_surface.py` (committed
// OpenAPI snapshot + generated src/api/schema.ts) and the contract fixtures
// exercised in the vitest suite. Timestamps stay the strings JSON carries, so
// the client never needs a date parser to read an API payload.

export type JsonObject = Record<string, unknown>

export interface EntityRef {
  entity_id: string
  type: string
  label: string
  properties: JsonObject
  ontology_version: string | null
  created_at: string | null
}

export interface EdgeRef {
  relation: string
  subject_id: string
  object_id: string
  validity_basis: string | null
  roster_snapshot_id: string | null
  source_id: string | null
  source_trust: number | null
  confidence: number | null
  recorded_at: string | null
  valid_from: string | null
  valid_to: string | null
  retracted_at: string | null
  assertion_id: string | null
  ontology_version: string | null
  extractor_model: string | null
  prompt_version: string | null
  schema_version: string | null
  evidence_document_id: string | null
  evidence_manifest_hash: string | null
  evidence_start: number | null
  evidence_end: number | null
  evidence_channel: string | null
  evidence_member: string | null
  evidence_row: number | null
  source_event_id: string | null
  source_url: string | null
  report_url: string | null
  source_recorded_at: string | null
  article_text_available: boolean | null
}

export interface GraphResult {
  nodes: EntityRef[]
  edges: EdgeRef[]
  counts: Record<string, number>
}

export interface CoverageReport {
  relation_counts: Record<string, number>
  contributing_sources: string[]
  source_refresh: Record<string, string | null>
}

export interface Diagnosis {
  note: string
  relation_counts: Record<string, number>
  failing_clause: string
  clause_index: number
}

export interface NlqOutcome {
  question: string
  cypher: string
  results: GraphResult | null
  validation_errors: string[]
  plan_rejection: JsonObject | null
  notes: string[]
}

export type BuilderDirection = "out" | "in"
export type TemporalQualifier = "current" | "as_of" | "as_believed"

export interface BuilderHop {
  relation: string
  direction: BuilderDirection
  target_type: string
  filters: JsonObject
  temporal_qualifier: TemporalQualifier | null
  temporal_instant: string | null
}

export interface BuilderSpec {
  start_type: string
  start_filters: JsonObject
  hops: BuilderHop[]
}

export interface HealthInfo {
  status: string
  neo4j: boolean
  ontology_version: string
}

export interface SearchHit {
  kind: string
  id: string
  label: string
  score: number
}

export interface EntityDetail {
  entity: EntityRef
  edge_summary: Record<string, Record<string, number>>
}

export interface NeighborRow {
  edge: EdgeRef
  neighbor: EntityRef
}

export interface GraphNeighbors {
  entity: EntityRef
  neighbors: NeighborRow[]
}

export interface SavedQuery {
  saved_query_id: string
  question: string
  cypher: string
  ontology_version: string
  result_count: number
  created_at: string
  pinned: boolean
}

export interface SourceInfo {
  source_id: string
  name: string
  kind: string
  trust_rank: number
  supports_backfill: boolean
  supports_incremental: boolean
  last_success_at: string | null
  last_run_id: string | null
}

export interface CostEntry {
  ledger_id: string
  period: string
  run_id: string | null
  purpose: string
  model_id: string
  input_tokens: number
  output_tokens: number
  cost_eur: number
  created_at: string
}

export interface CostLedger {
  period: string
  spend_eur: number
  entries: CostEntry[]
}

export interface IngestRun {
  source_id: string
  mode: string
  run_id: string
  started_at: string
  finished_at: string | null
  records_fetched: number
  nodes_created: number
  nodes_matched: number
  assertions_written: number
  assertions_skipped: number
  assertions_rejected: number
  documents_gated_out: number
  errors: number
  cost_eur: number
  last_success_at: string | null
}

export type QuerySurface = "cypher" | "builder" | "nl"

/** The executed-query outcome shared by the three query surfaces
 * (routers/query.py `QueryResponse` plus the NL envelope): results/coverage/
 * diagnosis stay null-able because /query/nl attaches none of them when
 * validation failed or the plan was rejected. The NL surface additionally
 * carries the full outcome (question, editable cypher, errors) on `nlq`.
 */
export interface QueryOutcome {
  source: QuerySurface
  cypher: string
  results: GraphResult | null
  coverage: CoverageReport | null
  diagnosis: Diagnosis | null
  notes: string[]
  nlq: NlqOutcome | null
}

export interface OperationRequest {
  request_id: string
  command: string
  identity_reviews?: JsonObject[]
  selections?: JsonObject[]
  extract_context?: boolean
  source?: string
  investigation_id?: string
  after_document?: string
  days?: number
  version?: string
  stage?: string
  evaluation?: string
}

export interface OperationJob {
  job_id: string
  request: OperationRequest
  status: string
  created_at: string
  updated_at: string
  output: string
  exit_code: number | null
}

export type NewsModality =
  | "asserted"
  | "reported"
  | "denied"
  | "proposed"
  | "conditional"
  | "unknown"

export type NewsAssessment = "unassessed" | "supported" | "disputed" | "refuted"

export type NewsEventStatus =
  | "unknown"
  | "proposed"
  | "planned"
  | "ongoing"
  | "completed"
  | "cancelled"
  | "denied"

export type NewsTimePrecision =
  | "unknown"
  | "instant"
  | "day"
  | "month"
  | "year"
  | "interval"

export interface NewsClaim {
  claim_id: string
  modality: NewsModality
  subject_id: string
  subject_label: string
  object_id: string
  object_label: string
  relation: string
  evidence_document_id: string
  attribution: string | null
  assessment: NewsAssessment
  event_status: NewsEventStatus
  time_precision: NewsTimePrecision
  event_candidate: string | null
  evidence_start: number | null
  evidence_end: number | null
  source_id: string | null
  source_trust: number | null
  confidence: number | null
  investigation_id: string | null
  dispatch_id: string | null
  publisher: string | null
  syndication_key: string | null
  report_url: string | null
  valid_from: string | null
  valid_to: string | null
  recorded_at: string | null
  retracted_at: string | null
  ontology_version: string | null
  prompt_version: string | null
  schema_version: string | null
  extractor_model: string | null
}

export interface NewsInvestigation {
  investigation_id: string
  title: string
  entity_ids: string[]
  assertion_ids: string[]
  active: boolean
  interval_minutes: number
  revision: number
  job_id: string | null
  next_due: string | null
  last_success: string | null
  status: "ready" | "queued" | "running" | "succeeded" | "failed" | "paused"
}

export interface DevelopmentEvidence {
  evidence_id: string
  kind: string
  subject_id: string
  object_id: string
  subject_label: string
  object_label: string
  relation: string
  properties: JsonObject
  dependency_key: string | null
}

export interface EventMatch {
  candidate_id: string
  left: string
  right: string
  decision: string
  assessment: string
  independence: string
  rationale: string | null
  review_id: string | null
}

export interface EventMatchReview {
  request_id: string
  left: string
  right: string
  decision: string
  rationale: string
  investigation_id: string
  recorded_at: string
  assessment: string
  independence: string
}

export interface DevelopmentView {
  investigation_id: string
  evidence: DevelopmentEvidence[]
  candidates: EventMatch[]
  reviews: EventMatchReview[]
  coverage: JsonObject
  locations: JsonObject[]
  truncated: boolean
  diagnosis: string[]
}

export interface EnrichmentResponse {
  entity_id: string
  snapshots: JsonObject[]
  truncated: boolean
  diagnosis: string[]
}

export interface ScopeCoverage {
  scope: string
  institution: string
  snapshot_id: string | null
  status: string
  observed_at: string | null
  term: string | null
  expected: number | null
  acquired: number
  loaded: number
  distinct_persons: number
  unresolved: number
  failed_rows: number | null
  stale: boolean | null
  check_basis: string | null
  diagnosis: string[]
}

export interface OfficesResponse {
  coverage_status: string
  scopes: ScopeCoverage[]
  members: JsonObject[]
  truncated: boolean
  diagnosis: string[]
}

export type NewsDocumentBundle = {
  record: JsonObject
  evidence: JsonObject[]
}

// -- Liner factories -------------------------------------------------------
// The API mirrors never invent values: every parse is fieldwise and labelled
// so a schema drift fails loudly (client bug contract, FR NFR-DC-074).

export function entityRefFromApi(d: JsonObject): EntityRef {
  return {
    entity_id: str(d.entity_id),
    type: str(d.type),
    label: str(d.label),
    properties: obj(d.properties),
    ontology_version: optStr(d.ontology_version),
    created_at: optStr(d.created_at),
  }
}

export function edgeRefFromApi(d: JsonObject): EdgeRef {
  return {
    relation: str(d.relation),
    subject_id: str(d.subject_id),
    object_id: str(d.object_id),
    validity_basis: optStr(d.validity_basis),
    roster_snapshot_id: optStr(d.roster_snapshot_id),
    source_id: optStr(d.source_id),
    source_trust: optNum(d.source_trust),
    confidence: optNum(d.confidence),
    recorded_at: optStr(d.recorded_at),
    valid_from: optStr(d.valid_from),
    valid_to: optStr(d.valid_to),
    retracted_at: optStr(d.retracted_at),
    assertion_id: optStr(d.assertion_id),
    ontology_version: optStr(d.ontology_version),
    extractor_model: optStr(d.extractor_model),
    prompt_version: optStr(d.prompt_version),
    schema_version: optStr(d.schema_version),
    evidence_document_id: optStr(d.evidence_document_id),
    evidence_manifest_hash: optStr(d.evidence_manifest_hash),
    evidence_start: optNum(d.evidence_start),
    evidence_end: optNum(d.evidence_end),
    evidence_channel: optStr(d.evidence_channel),
    evidence_member: optStr(d.evidence_member),
    evidence_row: optNum(d.evidence_row),
    source_event_id: optStr(d.source_event_id),
    source_url: optStr(d.source_url),
    report_url: optStr(d.report_url),
    source_recorded_at: optStr(d.source_recorded_at),
    article_text_available: optBool(d.article_text_available),
  }
}

export function graphResultFromApi(d: JsonObject): GraphResult {
  return {
    nodes: (arr(d.nodes) as JsonObject[]).map(entityRefFromApi),
    edges: (arr(d.edges) as JsonObject[]).map(edgeRefFromApi),
    counts: mapCount(d.counts),
  }
}

export function coverageReportFromApi(d: JsonObject): CoverageReport {
  return {
    relation_counts: mapCount(d.relation_counts),
    contributing_sources: (arr(d.contributing_sources) as (string | number)[]).map(
      (source) => str(source, "source"),
    ),
    source_refresh: obj(d.source_refresh) as Record<string, string | null>,
  }
}

export function diagnosisFromApi(d: JsonObject): Diagnosis {
  return {
    failing_clause: str(d.failing_clause),
    clause_index: num(d.clause_index),
    relation_counts: mapCount(d.relation_counts),
    note: str(d.note),
  }
}

export function nlqOutcomeFromApi(d: JsonObject): NlqOutcome {
  return {
    question: str(d.question),
    cypher: str(d.cypher),
    results: d.results != null ? graphResultFromApi(obj(d.results)) : null,
    validation_errors: (arr(d.validation_errors) as unknown[]).map(String),
    plan_rejection: (d.plan_rejection ?? null) as JsonObject | null,
    notes: (arr(d.notes) as unknown[]).map(String),
  }
}

export function healthInfoFromApi(d: JsonObject): HealthInfo {
  return {
    status: str(d.status),
    neo4j: bool(d.neo4j),
    ontology_version: str(d.ontology_version),
  }
}

export function searchHitFromApi(d: JsonObject): SearchHit {
  return {
    kind: str(d.kind),
    id: str(d.id),
    label: str(d.label),
    score: Number(d.score),
  }
}

export function entityDetailFromApi(d: JsonObject): EntityDetail {
  const summary: Record<string, Record<string, number>> = {}
  for (const [direction, counts] of Object.entries(obj(d.edge_summary))) {
    summary[direction] = mapCount(counts as JsonObject)
  }
  return { entity: entityRefFromApi(obj(d.entity)), edge_summary: summary }
}

export function graphNeighborsFromApi(d: JsonObject): GraphNeighbors {
  return {
    entity: entityRefFromApi(obj(d.entity)),
    neighbors: (arr(d.neighbors) as JsonObject[]).map((row) => ({
      edge: edgeRefFromApi(obj(row.edge)),
      neighbor: entityRefFromApi(obj(row.neighbor)),
    })),
  }
}

export function savedQueryFromApi(d: JsonObject): SavedQuery {
  return {
    saved_query_id: str(d.saved_query_id),
    question: str(d.question),
    cypher: str(d.cypher),
    ontology_version: str(d.ontology_version),
    result_count: num(d.result_count),
    created_at: str(d.created_at ?? ""),
    pinned: bool(d.pinned ?? false),
  }
}

export function sourceInfoFromApi(d: JsonObject): SourceInfo {
  return {
    source_id: str(d.source_id),
    name: str(d.name),
    kind: str(d.kind),
    trust_rank: Number(d.trust_rank),
    supports_backfill: bool(d.supports_backfill),
    supports_incremental: bool(d.supports_incremental),
    last_success_at: optStr(d.last_success_at),
    last_run_id: optStr(d.last_run_id),
  }
}

export function costLedgerFromApi(d: JsonObject): CostLedger {
  return {
    period: str(d.period),
    spend_eur: Number(d.spend_eur),
    entries: (arr(d.entries) as JsonObject[]).map((e) => ({
      ledger_id: str(e.ledger_id),
      period: str(e.period),
      run_id: optStr(e.run_id),
      purpose: str(e.purpose),
      model_id: str(e.model_id),
      input_tokens: num(e.input_tokens),
      output_tokens: num(e.output_tokens),
      cost_eur: Number(e.cost_eur),
      created_at: str(e.created_at ?? ""),
    })),
  }
}

export function ingestRunFromApi(d: JsonObject): IngestRun {
  return {
    source_id: str(d.source_id),
    mode: str(d.mode),
    run_id: str(d.run_id),
    started_at: str(d.started_at ?? ""),
    finished_at: optStr(d.finished_at),
    records_fetched: num(d.records_fetched ?? 0),
    nodes_created: num(d.nodes_created ?? 0),
    nodes_matched: num(d.nodes_matched ?? 0),
    assertions_written: num(d.assertions_written ?? 0),
    assertions_skipped: num(d.assertions_skipped ?? 0),
    assertions_rejected: num(d.assertions_rejected ?? 0),
    documents_gated_out: num(d.documents_gated_out ?? 0),
    errors: num(d.errors ?? 0),
    cost_eur: Number(d.cost_eur ?? 0),
    last_success_at: optStr(d.last_success_at),
  }
}

export function operationJobFromApi(d: JsonObject): OperationJob {
  return {
    job_id: str(d.job_id),
    request: opRequestFromApi(obj(d.request)),
    status: str(d.status),
    created_at: str(d.created_at ?? ""),
    updated_at: str(d.updated_at ?? ""),
    output: str(d.output ?? ""),
    exit_code: optNum(d.exit_code),
  }
}

function opRequestFromApi(d: JsonObject): OperationRequest {
  return {
    request_id: str(d.request_id),
    command: str(d.command),
    identity_reviews: optArr(d.identity_reviews),
    selections: optArr(d.selections),
    extract_context: optBool(d.extract_context) ?? undefined,
    source: optStr(d.source) ?? undefined,
    investigation_id: optStr(d.investigation_id) ?? undefined,
    after_document: optStr(d.after_document) ?? undefined,
    days: optNum(d.days) ?? undefined,
    version: optStr(d.version) ?? undefined,
    stage: optStr(d.stage) ?? undefined,
    evaluation: optStr(d.evaluation) ?? undefined,
  }
}

function optArr(value: unknown): JsonObject[] | undefined {
  if (value === null || value === undefined) return undefined
  const list = arr(value) as JsonObject[]
  return list.length ? list : undefined
}

export function newsClaimFromApi(d: JsonObject): NewsClaim {
  // Non-optional numeric/boolean fields fall back to the API defaults.
  return {
    modality: (str(d.modality) || "unknown") as NewsClaim["modality"],
    claim_id: str(d.claim_id),
    subject_id: str(d.subject_id),
    subject_label: str(d.subject_label),
    object_id: str(d.object_id),
    object_label: str(d.object_label),
    relation: str(d.relation),
    evidence_document_id: str(d.evidence_document_id),
    attribution: optStr(d.attribution),
    assessment: (str(d.assessment) || "unassessed") as NewsClaim["assessment"],
    event_status: (str(d.event_status) || "unknown") as NewsClaim["event_status"],
    time_precision: (str(d.time_precision) || "unknown") as NewsClaim["time_precision"],
    event_candidate: optStr(d.event_candidate),
    evidence_start: optNum(d.evidence_start),
    evidence_end: optNum(d.evidence_end),
    source_id: optStr(d.source_id),
    source_trust: optNum(d.source_trust),
    confidence: optNum(d.confidence),
    investigation_id: optStr(d.investigation_id),
    dispatch_id: optStr(d.dispatch_id),
    publisher: optStr(d.publisher),
    syndication_key: optStr(d.syndication_key),
    report_url: optStr(d.report_url),
    valid_from: optStr(d.valid_from),
    valid_to: optStr(d.valid_to),
    recorded_at: optStr(d.recorded_at),
    retracted_at: optStr(d.retracted_at),
    ontology_version: optStr(d.ontology_version),
    prompt_version: optStr(d.prompt_version),
    schema_version: optStr(d.schema_version),
    extractor_model: optStr(d.extractor_model),
  }
}

export function newsInvestigationFromApi(d: JsonObject): NewsInvestigation {
  return {
    investigation_id: str(d.investigation_id),
    title: str(d.title),
    entity_ids: (arr(d.entity_ids) as unknown[]).map(String),
    assertion_ids: (arr(d.assertion_ids) as unknown[]).map(String),
    active: bool(d.active ?? true),
    interval_minutes: num(d.interval_minutes ?? 60),
    revision: num(d.revision ?? 1),
    job_id: optStr(d.job_id),
    next_due: optStr(d.next_due),
    last_success: optStr(d.last_success),
    status: (str(d.status) || "ready") as NewsInvestigation["status"],
  }
}

export function developmentViewFromApi(d: JsonObject): DevelopmentView {
  return {
    investigation_id: str(d.investigation_id),
    evidence: (arr(d.evidence) as JsonObject[]).map((v) => ({
      evidence_id: str(v.evidence_id),
      kind: str(v.kind),
      subject_id: str(v.subject_id),
      object_id: str(v.object_id),
      subject_label: str(v.subject_label),
      object_label: str(v.object_label),
      relation: str(v.relation),
      properties: obj(v.properties),
      dependency_key: optStr(v.dependency_key),
    })),
    candidates: (arr(d.candidates) as JsonObject[]).map((v) => ({
      candidate_id: str(v.candidate_id),
      left: str(v.left),
      right: str(v.right),
      decision: str(v.decision ?? "unresolved"),
      assessment: str(v.assessment ?? "unassessed"),
      independence: str(v.independence ?? "unknown"),
      rationale: optStr(v.rationale),
      review_id: optStr(v.review_id),
    })),
    reviews: (arr(d.reviews) as JsonObject[]).map((v) => ({
      request_id: str(v.request_id),
      left: str(v.left),
      right: str(v.right),
      decision: str(v.decision),
      rationale: str(v.rationale),
      investigation_id: str(v.investigation_id),
      recorded_at: str(v.recorded_at ?? ""),
      assessment: str(v.assessment ?? "unassessed"),
      independence: str(v.independence ?? "unknown"),
    })),
    coverage: obj(d.coverage),
    locations: arr(d.locations) as JsonObject[],
    truncated: bool(d.truncated ?? false),
    diagnosis: (arr(d.diagnosis) as unknown[]).map(String),
  }
}

export function enrichmentFromApi(d: JsonObject): EnrichmentResponse {
  return {
    entity_id: str(d.entity_id),
    snapshots: arr(d.snapshots) as JsonObject[],
    truncated: bool(d.truncated ?? false),
    diagnosis: (arr(d.diagnosis) as unknown[]).map(String),
  }
}

export function officesFromApi(d: JsonObject): OfficesResponse {
  return {
    coverage_status: str(d.coverage_status ?? "partial"),
    scopes: (arr(d.scopes) as JsonObject[]).map((s) => ({
      scope: str(s.scope),
      institution: str(s.institution),
      snapshot_id: optStr(s.snapshot_id),
      status: str(s.status ?? "missing"),
      observed_at: optStr(s.observed_at),
      term: optStr(s.term),
      expected: optNum(s.expected),
      acquired: num(s.acquired ?? 0),
      loaded: num(s.loaded ?? 0),
      distinct_persons: num(s.distinct_persons ?? 0),
      unresolved: num(s.unresolved ?? 0),
      failed_rows: optNum(s.failed_rows),
      stale: optBool(s.stale),
      check_basis: optStr(s.check_basis),
      diagnosis: (arr(s.diagnosis) as unknown[]).map(String),
    })),
    members: arr(d.members) as JsonObject[],
    truncated: bool(d.truncated ?? false),
    diagnosis: (arr(d.diagnosis) as unknown[]).map(String),
  }
}

// -- parsing helpers (fail loudly, never default silently) ----------------

export function toStringValue(value: unknown, field: string): string {
  if (typeof value !== "string" || value === "") {
    throw new TypeError(`client mirror expects a string for ${field}`)
  }
  return value
}
export const str = (v: unknown, field = "value") => toStringValue(v, field)

export function toNumber(value: unknown, field: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`client mirror expects a finite number for ${field}`)
  }
  return value
}
export const num = (v: unknown, field = "value") => toNumber(v, field)

export function toBool(value: unknown, field: string): boolean {
  if (typeof value !== "boolean") {
    throw new TypeError(`client mirror expects a boolean for ${field}`)
  }
  return value
}
export const bool = (v: unknown, field = "value") => toBool(v, field)

export function optStr(value: unknown): string | null {
  return typeof value === "string" ? value : null
}
export function optNum(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}
export function optBool(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null
}
export function arr(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}
export function obj(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {}
}
export function mapCount(value: unknown): Record<string, number> {
  const out: Record<string, number> = {}
  for (const [key, count] of Object.entries(obj(value))) {
    const n = Number(count)
    if (Number.isFinite(n)) out[key] = n
  }
  return out
}
