// src/state/__tests__/payloads.test.ts
// Pins for the viz payload builders (ports of the retired bridge): the map
// treats GeoJSON's ordering (Leaflet wants lat,lon), missing geometry is
// counted explicitly, timeline splits validity/belief instants, and a
// claim artifact with unknown event time contributes only its belief time.

import { describe, expect, it } from "vitest"

import type { CoverageReport, EdgeRef, EntityRef } from "@/api/types"
import { geometryOf, mapPayload, networkPayload, timelinePayload } from "../payloads"
import { resultFromApi } from "../temporal"

const COVERAGE: CoverageReport = {
  relation_counts: { PURPLE_LADDER: 1 },
  contributing_sources: ["openregister"],
  source_refresh: { openregister: "2026-01-01" },
}

const baseNode: EntityRef = {
  entity_id: "a",
  type: "AardvarkSong",
  label: "Alpha",
  properties: {},
  ontology_version: "1.4.0",
  created_at: null,
}

function node(over: Partial<EntityRef>): EntityRef {
  return { ...baseNode, ...over, properties: { ...over.properties } }
}

function edge(over: Partial<EdgeRef>): EdgeRef {
  const base = {
    relation: "PURPLE_LADDER",
    subject_id: "a",
    object_id: "b",
    validity_basis: null,
    roster_snapshot_id: null,
    source_id: "openregister",
    source_trust: 1,
    confidence: 0.9,
    recorded_at: "2024-03-01T10:00:00Z",
    valid_from: "2024-01-01",
    valid_to: "2025-01-01",
    retracted_at: null,
    assertion_id: "assert-1",
    ontology_version: "1.4.0",
    extractor_model: null,
    prompt_version: null,
    schema_version: null,
    evidence_document_id: null,
    evidence_manifest_hash: null,
    evidence_start: null,
    evidence_end: null,
    evidence_channel: null,
    evidence_member: null,
    evidence_row: null,
    source_event_id: null,
    source_url: null,
    report_url: null,
    source_recorded_at: null,
    article_text_available: null,
  }
  return { ...base, ...over }
}

describe("geometryOf", () => {
  it("returns latitude first, validating the ranges (Leaflet, not GeoJSON)", () => {
    expect(geometryOf(node({ properties: { latitude: 52.5, longitude: 13.4 } }))).toEqual([
      52.5, 13.4,
    ])
    expect(geometryOf(node({ properties: { latitude: 100, longitude: 13.4 } }))).toBeNull()
    expect(geometryOf(node({ properties: { latitude: "nope", longitude: 13.4 } }))).toBeNull()
    expect(geometryOf(node({ properties: {} }))).toBeNull()
  })
})

describe("networkPayload", () => {
  it("maps refs to plain data and copies the coverage report", () => {
    const result = resultFromApi({
      nodes: [node({ properties: { claim_id: "c1", modality: "denied", source_trust: 0.5 } })],
      edges: [edge({})],
      counts: { rows: 2 },
    })
    const payload = networkPayload(result, COVERAGE)
    expect(payload.nodes[0]).toMatchObject({
      id: "a",
      type: "AardvarkSong",
      label: "Alpha",
      claim: { modality: "denied", source_trust: 0.5, confidence: null },
    })
    expect(payload.edges[0]).toMatchObject({
      source: "a",
      target: "b",
      relation: "PURPLE_LADDER",
      belief_recorded_at: "2024-03-01T10:00:00Z",
    })
    expect(payload.coverage?.relation_counts).toEqual({ PURPLE_LADDER: 1 })
  })
})

describe("mapPayload", () => {
  it("counts missing geometry explicitly and keeps only selected edges' lines", () => {
    const result = resultFromApi({
      nodes: [
        node({ entity_id: "a", properties: { latitude: 52.5, longitude: 13.4 } }),
        node({ entity_id: "b", properties: {} }),
        node({ entity_id: "c", properties: { latitude: 51.0, longitude: 9.9 } }),
      ],
      edges: [
        edge({}),
        edge({ subject_id: "a", object_id: "c", assertion_id: "assert-2" }),
      ],
      counts: { rows: 3 },
    })
    const payload = mapPayload(result, COVERAGE, "a")
    // A line exists only where BOTH endpoints carry geometry: the edge into
    // the geometry-less b draws nothing (missing geometry is explicit, not
    // invented), while the a→c edge draws one.
    expect(payload.nodes).toHaveLength(2) // b has no coordinates
    expect(payload.missing_geometry).toBe(1)
    expect(payload.lines).toHaveLength(1)
    expect(payload.lines[0]).toMatchObject({ source: "a", target: "c", relation: "PURPLE_LADDER" })
  })
})

describe("timelinePayload", () => {
  it("splits validity and belief instants per assertion", () => {
    const result = resultFromApi({
      nodes: [],
      edges: [edge({ recorded_at: "2024-03-01T10:00:00Z", valid_from: "2024-01-01" })],
      counts: { rows: 1 },
    })
    const payload = timelinePayload(result, COVERAGE)
    expect(payload.validity).toHaveLength(1)
    expect(payload.belief).toHaveLength(1)
    expect(payload.validity[0].kind).toBe("validity")
    expect(payload.belief[0].t).toBe("2024-03-01T10:00:00Z")
  })

  it("contributes only belief time for a claim with unknown event precision", () => {
    const result = resultFromApi({
      nodes: [
        node({
          entity_id: "claim-1",
          properties: {
            claim_id: "claim-1",
            time_precision: "unknown",
            valid_from: "2024-02-15",
            recorded_at: "2024-03-01T09:00:00Z",
            modality: "proposed",
          },
        }),
      ],
      edges: [],
      counts: { rows: 1 },
    })
    const payload = timelinePayload(result, COVERAGE)
    expect(payload.validity).toHaveLength(0)
    expect(payload.belief).toHaveLength(1)
    expect(payload.belief[0]).toMatchObject({
      assertion_id: "claim-1",
      kind: "belief",
      event_status: undefined,
      time_precision: "unknown",
    })
  })

  it("respects the applied validity window", () => {
    const result = resultFromApi({
      nodes: [],
      edges: [edge({ valid_from: "2025-06-01" })],
      counts: { rows: 1 },
    })
    const payload = timelinePayload(result, COVERAGE, "2025-01-01", "2025-12-31")
    expect(payload.validity).toHaveLength(1)
    expect(timelinePayload(result, COVERAGE, "2024-01-01", "2024-12-31").validity).toHaveLength(0)
  })
})
