// src/state/__tests__/temporal.test.ts
// Bitemporal visibility pins (FR-DC-042/043, DC-14): validity bounds
// intersect independently from the belief axis; unknown timestamps stay
// visible; date-only bounds become end-of-day instants; an unknown event
// time on a claim artifact contributes no validity instant.

import { describe, expect, it } from "vitest"

import type { EdgeRef, EntityRef } from "@/api/types"
import { EMPTY_TEMPORAL, edgeVisible, instantOf, resultFromApi, temporalBundle } from "../temporal"

function edge(over: Partial<EdgeRef> = {}): EdgeRef {
  return {
    relation: "PURPLE_LADDER",
    subject_id: "a",
    object_id: "b",
    validity_basis: null,
    roster_snapshot_id: null,
    source_id: "ledger",
    source_trust: 1,
    confidence: 1,
    recorded_at: "2024-03-01T10:00:00Z",
    valid_from: "2024-01-01",
    valid_to: null,
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
    ...over,
  }
}

function claimNode(over: Record<string, unknown> = {}): EntityRef {
  return {
    entity_id: "claim-1",
    type: "AardvarkSong",
    label: "claim",
    properties: {
      claim_id: "claim-1",
      time_precision: "instant",
      valid_from: "2024-02-15",
      recorded_at: "2024-03-01T09:00:00Z",
      ...over,
    },
    ontology_version: "1.4.0",
    created_at: null,
  }
}

describe("instantOf", () => {
  it("treats date-only strings as UTC instants and pushes end-of-day bounds", () => {
    expect(instantOf("2024-01-05", { endOfDay: true })?.toISOString()).toBe(
      "2024-01-05T23:59:59.999Z",
    )
    expect(instantOf("2024-01-05T00:00:00Z", { endOfDay: true })?.toISOString()).toBe(
      "2024-01-05T00:00:00.000Z",
    )
  })

  it("rejects non-ISO junk instead of letting Date guess", () => {
    expect(instantOf("01/02/2024")).toBeNull()
    expect(instantOf(12345)).toBeNull()
  })
})

describe("edge visibility", () => {
  it("keeps an edge intersecting the validity window", () => {
    const filter = { ...EMPTY_TEMPORAL, validity_from: "2024-01-10", validity_to: "2024-02-28" }
    expect(edgeVisible(edge({ valid_from: "2024-02-01" }), filter)).toBe(true)
    expect(edgeVisible(edge({ valid_from: "2024-03-01", valid_to: "2024-03-05" }), filter)).toBe(
      false,
    )
  })

  it("applies the belief axis on recorded/retracted instants only", () => {
    const filter = { ...EMPTY_TEMPORAL, belief_as_of: "2024-02-01" }
    // Recorded after the belief point is invisible even with the same validity.
    expect(edgeVisible(edge({ recorded_at: "2024-02-02T00:00:00Z" }), filter)).toBe(false)
    // Retracted before the belief point is invisible.
    expect(
      edgeVisible(
        edge({ recorded_at: "2024-01-01T00:00:00Z", retracted_at: "2024-01-15T00:00:00Z" }),
        filter,
      ),
    ).toBe(false)
    // A never-recorded (unknown) assertion stays visible on the belief axis.
    expect(edgeVisible(edge({ recorded_at: null, retracted_at: null }), filter)).toBe(true)
  })

  it("validity-only bounds reject an interval disjoint on the start side", () => {
    // [2024-01-01, ∞) intersected with the window ending before 2024-01-01
    // is empty — a real disjoint case, not a one-sided open-interval slice.
    const filter = { ...EMPTY_TEMPORAL, validity_to: "2023-12-31" }
    expect(edgeVisible(edge({ valid_from: "2024-01-08" }), filter)).toBe(false)
    expect(edgeVisible(edge({ valid_from: null, valid_to: "2023-01-01" }), filter)).toBe(true)
  })

  it("the axes stay independent: a validity miss is never rescued by the belief axis", () => {
    const backdated = edge({ valid_from: "2024-06-05", recorded_at: null, retracted_at: null })
    expect(edgeVisible(backdated, { ...EMPTY_TEMPORAL, validity_to: "2023-12-31" })).toBe(false)
    expect(edgeVisible(backdated, { ...EMPTY_TEMPORAL, belief_as_of: "2021-05-01" })).toBe(true)
  })
})

describe("temporalBundle", () => {
  function plainNode(entityId: string): EntityRef {
    return {
      entity_id: entityId,
      type: "AardvarkSong",
      label: entityId,
      properties: {},
      ontology_version: "1.4.0",
      created_at: null,
    }
  }

  it("drops an incident endpoint whose only surviving edge is filtered away", () => {
    const result = resultFromApi({
      nodes: [plainNode("a"), plainNode("late"), plainNode("late2")],
      edges: [
        edge({}),
        edge({ subject_id: "late", object_id: "late2", assertion_id: "late-edge",
               valid_from: "2025-01-01" }),
      ],
      counts: { rows: 3 },
    })
    const filtered = temporalBundle(result, {
      ...EMPTY_TEMPORAL,
      validity_to: "2024-06-30", // the 2025 edge is outside the window
    })
    // The 2025 edge is gone, so BOTH of its endpoints (retained only
    // through it) drop; the anchor of the surviving edge stays.
    expect(filtered.edges.map((row) => row.assertion_id)).toEqual(["assert-1"])
    expect(filtered.nodes.map((node) => node.entity_id)).toEqual(["a"])
  })

  it("keeps a plain node without edges (it is graph context, not edge cargo)", () => {
    const result = resultFromApi({
      nodes: [plainNode("isolated")],
      edges: [],
      counts: { rows: 1 },
    })
    const filtered = temporalBundle(result, {
      ...EMPTY_TEMPORAL,
      belief_as_of: "2024-06-01",
    })
    expect(filtered.nodes.map((node) => node.entity_id)).toEqual(["isolated"])
  })

  it("ignores the validity instant of an unknown-precision claim artifact", () => {
    const result = resultFromApi({
      nodes: [claimNode({ time_precision: "unknown" })],
      edges: [],
      counts: { rows: 1 },
    })
    const filtered = temporalBundle(result, {
      ...EMPTY_TEMPORAL,
      // The claim has valid_from 2024-02-15; this bound excludes it by
      // validity — but the unknown event time contributes no instant, so
      // the node stays visible on its own recorded_at axis.
      validity_from: "2024-12-01",
    })
    expect(filtered.nodes).toHaveLength(1)
  })

  it("filters a qualified claim by its own validity and recorded times", () => {
    const result = resultFromApi({
      nodes: [claimNode()],
      edges: [],
      counts: { rows: 1 },
    })
    const kept = temporalBundle(result, { ...EMPTY_TEMPORAL, validity_to: "2024-03-31" })
    expect(kept.nodes.map((n) => n.entity_id)).toEqual(["claim-1"])
    const dropped = temporalBundle(result, { ...EMPTY_TEMPORAL, belief_as_of: "2024-02-01" })
    expect(dropped.nodes).toHaveLength(0)
  })

  it("returns the identical result for the empty filter", () => {
    const result = resultFromApi({ nodes: [], edges: [edge()], counts: { rows: 1 } })
    expect(temporalBundle(result, EMPTY_TEMPORAL)).toBe(result)
  })
})
