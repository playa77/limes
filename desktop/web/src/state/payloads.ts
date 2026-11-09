// src/state/payloads.ts
// Ports of the retired `limes_desktop.views.viz.bridge` payload builders.
// The network/map/timeline views consume these plain data shapes; the viz
// components never issue queries themselves (architecture §2.2).

import type {
  CoverageReport,
  EntityRef,
  GraphResult,
} from "@/api/types"
import { temporalBundle } from "@/state/temporal"
import type { TemporalFilter } from "@/state/temporal"

export interface ClaimMeta {
  modality: string | null
  attribution: string | null
  assessment: string | null
  event_status: string | null
  time_precision: string | null
  event_candidate: string | null
  evidence_document_id: string | null
  source_trust: number | null
  confidence: number | null
}

export interface NetworkNode {
  id: string
  type: string
  label: string
  claim: ClaimMeta | null
}

export interface NetworkEdge {
  source: string
  target: string
  relation: string
  confidence: number | null
  assertion_id: string | null
  valid_from: string | null
  valid_to: string | null
  belief_recorded_at: string | null
}

export interface NetworkPayload {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
  coverage: { relation_counts: Record<string, number>; contributing_sources: string[] } | null
}

export interface MapNode {
  id: string
  type: string
  label: string
  geometry: [number, number]
}

export interface MapLine {
  points: [number, number][]
  relation: string
  selected: boolean
  source: string
  target: string
}

export interface MapPayload {
  nodes: MapNode[]
  lines: MapLine[]
  coverage: NetworkPayload["coverage"]
  missing_geometry: number
}

export interface TimelinePoint {
  relation: string
  source: string | null
  target: string | null
  assertion_id: string
  t: string
  kind: "validity" | "belief"
  event_status?: string
  time_precision?: string
}

export interface TimelinePayload {
  validity: TimelinePoint[]
  belief: TimelinePoint[]
  coverage: NetworkPayload["coverage"]
}

const CLAIM_KEYS: (keyof ClaimMeta)[] = [
  "modality",
  "attribution",
  "assessment",
  "event_status",
  "time_precision",
  "event_candidate",
  "evidence_document_id",
  "source_trust",
  "confidence",
]

function claimMetaOf(node: EntityRef): ClaimMeta | null {
  if (typeof node.properties.claim_id !== "string") return null
  const meta = {} as Record<keyof ClaimMeta, unknown>
  for (const key of CLAIM_KEYS) {
    const value = node.properties[key as string]
    meta[key] =
      key === "source_trust" || key === "confidence"
        ? typeof value === "number" && Number.isFinite(value)
          ? value
          : null
        : value ?? null
  }
  return meta as ClaimMeta
}

export function claimOfMeta(node: EntityRef): ClaimMeta | null {
  return claimMetaOf(node)
}

/** Leaflet uses latitude, longitude; GeoJSON is reversed (DC-14). */
export function geometryOf(node: EntityRef): [number, number] | null {
  const lat = node.properties.latitude
  const lon = node.properties.longitude
  if (lat === undefined || lat === null || lon === undefined || lon === null) return null
  const latitude = Number(lat)
  const longitude = Number(lon)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null
  if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) return null
  return [latitude, longitude]
}

export function coverageOf(coverage: CoverageReport | null): NetworkPayload["coverage"] {
  return coverage
    ? {
        relation_counts: { ...coverage.relation_counts },
        contributing_sources: [...coverage.contributing_sources],
      }
    : null
}

export function networkPayload(
  result: GraphResult,
  coverage: CoverageReport | null,
): NetworkPayload {
  return {
    nodes: result.nodes.map((node) => ({
      id: node.entity_id,
      type: node.type,
      label: node.label,
      claim: claimMetaOf(node),
    })),
    edges: result.edges.map((edge) => ({
      source: edge.subject_id,
      target: edge.object_id,
      relation: edge.relation,
      confidence: edge.confidence,
      assertion_id: edge.assertion_id,
      valid_from: edge.valid_from,
      valid_to: edge.valid_to,
      belief_recorded_at: edge.recorded_at,
    })),
    coverage: coverageOf(coverage),
  }
}

/** FR-DC-041: point-geometry markers plus the selected entity's geo lines. */
export function mapPayload(
  result: GraphResult,
  coverage: CoverageReport | null,
  selectedId: string | null = null,
): MapPayload {
  const byId = new Map(result.nodes.map((n) => [n.entity_id, n]))
  const nodes: MapNode[] = []
  for (const node of result.nodes) {
    const geometry = geometryOf(node)
    if (geometry) nodes.push({ id: node.entity_id, type: node.type, label: node.label, geometry })
  }
  const lines: MapLine[] = []
  for (const edge of result.edges) {
    if (selectedId === null || (edge.subject_id !== selectedId && edge.object_id !== selectedId)) {
      continue
    }
    const a = byId.has(edge.subject_id) ? geometryOf(byId.get(edge.subject_id)!) : null
    const b = byId.has(edge.object_id) ? geometryOf(byId.get(edge.object_id)!) : null
    if (a === null || b === null) continue
    lines.push({
      points: [a, b],
      relation: edge.relation,
      selected: true,
      source: edge.subject_id,
      target: edge.object_id,
    })
  }
  return {
    nodes,
    lines,
    coverage: coverageOf(coverage),
    missing_geometry: result.nodes.length - nodes.length,
  }
}

/** FR-DC-042: one point per assertion instant; validity vs belief split, with
 *  qualified artifacts separate and unknown event time contributing belief
 *  time only. */
export function timelinePayload(
  result: GraphResult,
  coverage: CoverageReport | null,
  validityFrom: string | null = null,
  validityTo: string | null = null,
): TimelinePayload {
  const validity: TimelinePoint[] = []
  const belief: TimelinePoint[] = []
  const within = (instant: string): boolean =>
    (validityFrom === null || instant >= validityFrom) &&
    (validityTo === null || instant <= validityTo)
  for (const edge of result.edges) {
    const base = {
      relation: edge.relation,
      source: edge.subject_id,
      target: edge.object_id,
      assertion_id: edge.assertion_id ?? "",
    }
    if (edge.valid_from && within(edge.valid_from)) {
      validity.push({ ...base, t: edge.valid_from, kind: "validity" })
    }
    if (edge.recorded_at && within(edge.recorded_at)) {
      belief.push({ ...base, t: edge.recorded_at, kind: "belief" })
    }
  }
  for (const node of result.nodes) {
    if (typeof node.properties.claim_id !== "string") continue
    const props = node.properties
    const base = {
      relation: `${props.modality ?? "unknown"}: ${props.relation ?? ""}`,
      source: typeof props.subject_id === "string" ? props.subject_id : null,
      target: typeof props.object_id === "string" ? props.object_id : null,
      assertion_id: String(props.claim_id),
      event_status: typeof props.event_status === "string" ? props.event_status : undefined,
      time_precision: typeof props.time_precision === "string" ? props.time_precision : "unknown",
    } as const
    if (base.time_precision === "unknown") {
      // Unknown event time contributes only belief time (DC-16).
      const recorded = props.recorded_at
      if (typeof recorded === "string" && within(recorded)) {
        belief.push({ ...base, t: recorded, kind: "belief" })
      }
      continue
    }
    const instant = props.valid_from
    if (typeof instant === "string" && within(instant)) {
      validity.push({ ...base, t: instant, kind: "validity" })
    }
    const recordedAt = props.recorded_at
    if (typeof recordedAt === "string" && within(recordedAt)) {
      belief.push({ ...base, t: recordedAt, kind: "belief" })
    }
  }
  return { validity, belief, coverage: coverageOf(coverage) }
}

/** Shared temporal view application before payload building (FR-DC-043). */
export function bundleWithTemporal(
  result: GraphResult,
  coverage: CoverageReport | null,
  filter: TemporalFilter,
): { result: GraphResult; coverage: CoverageReport | null } {
  const filtered = temporalBundle(result, filter)
  return { result: filtered, coverage }
}
