// src/state/temporal.ts
// Bitemporal visibility logic (FR-DC-042/043, DC-14): intersect validity
// intervals; belief uses recorded/retracted instants independently in UTC.
// Unknown timestamps remain unknown/visible — never synthesized from the
// other axis. Pure functions so the vitest suite pins the semantics.

import type { EdgeRef, GraphResult } from "@/api/types"
import { graphResultFromApi } from "@/api/types"

export interface TemporalFilter {
  /** Inclusive lower validity bound (ISO string or date-only) or null. */
  validity_from: string | null
  /** Inclusive upper validity bound (date-only becomes end of day) or null. */
  validity_to: string | null
  /** Belief-as-of instant: only assertions recorded at/before and not
   *  retracted before it are visible, or null for "all recorded facts". */
  belief_as_of: string | null
}

export const EMPTY_TEMPORAL: TemporalFilter = {
  validity_from: null,
  validity_to: null,
  belief_as_of: null,
}

/** Parse an ISO instant (Z offsets included); date-only strings become UTC
 *  instants, with `endOfDay` pushing a date onto the last microsecond. */
export function instantOf(
  value: unknown,
  { endOfDay = false }: { endOfDay?: boolean } = {},
): Date | null {
  if (typeof value !== "string" || value === "") return null
  const normalized = value.replace("Z", "+00:00")
  // Date-only strings: `new Date("2024-01-05")` treats as UTC midnight.
  const dateOnly = /^\d{4}-\d{2}-\d{2}$/.test(normalized)
  const pre = dateOnly && /^\d{4}-\d{2}-\d{2}$/.test(normalized)
  if (!pre && !/^\d{4}-\d{2}-\d{2}(T|$|-)/.test(normalized)) {
    // The Python mirror rejects non-ISO shapes silently; do the same for
    // CSV-style junk that Date would otherwise guess at.
    return null
  }
  const parsed = new Date(normalized)
  if (Number.isNaN(parsed.getTime())) return null
  if (endOfDay && dateOnly) parsed.setTime(parsed.getTime() + 86_399_999)
  return parsed
}

export function isUtcInstant(date: Date): Date {
  return date
}

interface TemporalValues {
  valid_from: unknown
  valid_to: unknown
  recorded_at: unknown
  retracted_at: unknown
}

function visible(values: TemporalValues, filter: TemporalFilter): boolean {
  const lower = instantOf(filter.validity_from)
  const upper = instantOf(filter.validity_to, { endOfDay: true })
  const belief = instantOf(filter.belief_as_of, { endOfDay: true })
  const start = values.valid_from != null ? instantOf(values.valid_from) : null
  const end = values.valid_to != null ? instantOf(values.valid_to) : null
  const recorded = values.recorded_at != null ? instantOf(values.recorded_at) : null
  const retracted = values.retracted_at != null ? instantOf(values.retracted_at) : null
  return !(
    (upper !== null && start !== null && start > upper) ||
    (lower !== null && end !== null && end <= lower) ||
    (belief !== null && recorded !== null && recorded > belief) ||
    (belief !== null && retracted !== null && retracted <= belief)
  )
}

/** Claim-artifact nodes are filtered on their own recorded/retracted times
 *  with their validity times, exactly like edges. */
export function temporalBundle(
  result: GraphResult,
  filter: TemporalFilter,
): GraphResult {
  if (filter.validity_from === null && filter.validity_to === null && filter.belief_as_of === null) {
    return result
  }
  const edges = result.edges.filter((edge) => visible(edge, filter))
  const incident = new Set<string>()
  for (const edge of result.edges) {
    incident.add(edge.subject_id)
    incident.add(edge.object_id)
  }
  const retained = new Set<string>()
  for (const edge of edges) {
    retained.add(edge.subject_id)
    retained.add(edge.object_id)
  }
  const nodes = result.nodes.filter((node) => {
    // Incident endpoints that no surviving edge retains drop off; pure
    // node-only claim artifacts keep their own temporal check.
    if (incident.has(node.entity_id) && !retained.has(node.entity_id)) return false
    if (typeof node.properties.claim_id === "string") {
      const unknownTime = node.properties.time_precision === "unknown"
      const values: TemporalValues = {
        valid_from: node.properties.valid_from,
        valid_to: node.properties.valid_to,
        recorded_at: node.properties.recorded_at,
        retracted_at: node.properties.retracted_at,
      }
      if (unknownTime && values.valid_from != null) {
        // Unknown event time contributes no validity instant (DC-14).
        values.valid_from = null
      }
      return visible(values, filter)
    }
    return true
  })
  return { nodes, edges, counts: { ...result.counts } }
}

/** Rebuild a GraphResult from the mirrored API payload (parity fixture path). */
export function resultFromApi(payload: unknown): GraphResult {
  if (typeof payload !== "object" || payload === null) {
    throw new TypeError("graph result expected")
  }
  return graphResultFromApi(payload as Record<string, unknown>)
}

export function edgeVisible(edge: EdgeRef, filter: TemporalFilter): boolean {
  return visible(edge, filter)
}
