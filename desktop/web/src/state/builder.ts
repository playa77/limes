// src/state/builder.ts
// TS port of the retired `limes_desktop.views.query_builder`: every option is
// computed from the GET /builder/schema projection with the exact
// relations_for/targets_for semantics the Dash UI used (domain side => out,
// range side => in, supertype-expanded concrete types). The refill rules are
// DC-14's:
//   - a relation change refills the admissible directions (+ downstream),
//   - a direction change does NOT refill/reset the relation,
//   - every refill retains still-admissible selections, picks the first
//     schema option when a choice becomes invalid, and recomputes the whole
//     downstream suffix,
//   - submission rechecks every hop triple before posting the spec.

import type { JsonObject } from "@/api/types"
import type { BuilderDirection } from "@/api/types"

export interface BuilderSchemaEntry {
  name: string
  supertype?: string | null
  [key: string]: unknown
}

export interface Schema {
  entity_types: BuilderSchemaEntry[]
  relation_types: {
    name: string
    domain: string[]
    range: string[]
    [key: string]: unknown
  }[]
}

export interface HopState {
  relation: string | null
  direction: BuilderDirection | null
  target_type: string | null
}

export interface DerivedOptions {
  relations: string[]
  directions: BuilderDirection[]
  targets: string[]
}

export const DIRECTION_LABELS: Record<BuilderDirection, string> = {
  out: "outgoing",
  in: "incoming",
}

class SchemaIndex {
  private readonly entities: Map<string, BuilderSchemaEntry>
  private readonly relations: Map<string, { domain: string[]; range: string[] }>

  constructor(schema: Schema) {
    this.entities = new Map(schema.entity_types.map((entry) => [entry.name, entry]))
    this.relations = new Map(
      schema.relation_types.map((entry) => [entry.name, { domain: entry.domain, range: entry.range }]),
    )
  }

  supertypeChain(typeName: string): string[] {
    const chain: string[] = []
    let current: string | undefined | null = this.entities.get(typeName)?.supertype
    while (current !== null && current !== undefined) {
      chain.push(current)
      const next: string | null | undefined = this.entities.get(current)?.supertype
      current = typeof next === "string" ? next : null
    }
    return chain
  }

  admitted(declared: string[], typeName: string): boolean {
    if (typeName.length === 0) return false
    if (declared.includes(typeName)) return true
    return this.supertypeChain(typeName).some((s) => declared.includes(s))
  }

  admittedTypes(relation: string, side: "domain" | "range"): string[] {
    const declared = this.relations.get(relation)?.[side] ?? []
    const concrete = [...this.entities.keys()]
    const admitted: string[] = []
    for (const name of declared) {
      if (concrete.includes(name) && !admitted.includes(name)) admitted.push(name)
      for (const candidate of concrete) {
        if (!admitted.includes(candidate) && this.supertypeChain(candidate).includes(name)) {
          admitted.push(candidate)
        }
      }
    }
    return admitted
  }

  directionsFor(typeName: string, relation: string): BuilderDirection[] {
    const spec = this.relations.get(relation)
    if (!spec) return []
    const directions: BuilderDirection[] = []
    if (this.admitted(spec.domain, typeName)) directions.push("out")
    if (this.admitted(spec.range, typeName)) directions.push("in")
    return directions
  }

  targetsFor(relation: string, direction: BuilderDirection): string[] {
    return this.admittedTypes(relation, direction === "out" ? "range" : "domain")
  }

  /** Relations admissible from `typeName` at all (first dropdown hop option). */
  relationsFor(typeName: string): string[] {
    return [...this.relations.keys()].filter(
      (relation) => this.directionsFor(typeName, relation).length > 0,
    )
  }
}

export function createIndex(schema: Schema): SchemaIndex {
  return new SchemaIndex(schema)
}

/**
 * refillHop: the single recompute point for one hop row's option sets plus
 * selection normalization. `previous` is retained when still admissible;
 * otherwise the first schema option is chosen (or null when none exists).
 * The relation is only refilled when `refillRelation` is set — a direction
 * change never discards the user's relation (DC-14).
 */
export function refillHop(
  index: SchemaIndex,
  currentType: string,
  previous: HopState,
  refillRelation: boolean,
): HopState & DerivedOptions {
  const relations = index.relationsFor(currentType)
  const next: HopState = {
    relation: previous.relation,
    direction: previous.direction,
    target_type: previous.target_type,
  }
  if (refillRelation) {
    next.relation = selectedIn(previous.relation, relations)
  }
  const directions =
    next.relation !== null ? index.directionsFor(currentType, next.relation) : []
  next.direction = selectedIn(previous.direction, directions)
  const targets =
    next.relation !== null && next.direction !== null
      ? index.targetsFor(next.relation, next.direction)
      : []
  next.target_type = selectedIn(previous.target_type, targets)
  return {
    relation: next.relation,
    direction: next.direction,
    target_type: next.target_type,
    relations,
    directions,
    targets,
  }
}

function selectedIn<T extends string>(previous: T | null, allowed: T[]): T | null {
  if (previous !== null && allowed.includes(previous)) return previous
  return allowed.length > 0 ? allowed[0] : null
}

export interface BuilderState {
  start_type: string | null
  hops: (HopState & DerivedOptions)[]
}

/**
 * Refill the downstream chain starting at `fromHop`. Mirrors the Qt view's
 * `_refresh_hop` + `_refresh_chain_from`: the hop where the user acted keeps
 * its own refill flag (a relation or direction change does NOT re-pick the
 * relation: refillRelation = false there; a start-type change or a fresh
 * refill sets it true), and every hop after it recomputes with relation
 * refill on, retaining still-admissible selections.
 */
export function refreshFrom(
  index: SchemaIndex,
  startType: string | null,
  hops: HopState[],
  fromHop: number,
  refillRelationFlags?: (boolean | undefined)[],
): BuilderState {
  const at = (i: number): boolean => {
    const flag = refillRelationFlags?.[i]
    if (flag !== undefined) return flag
    return i > fromHop
  }
  const derived: (HopState & DerivedOptions)[] = hops.map((hop) => ({
    relation: hop.relation,
    direction: hop.direction,
    target_type: hop.target_type,
    relations: [],
    directions: [],
    targets: [],
  }))
  let current: string | null = startType
  for (let i = 0; i < derived.length; i++) {
    if (i < fromHop) {
      current = derived[i].target_type
      continue
    }
    derived[i] = refillHop(index, current ?? "", hops[i], at(i))
    current = derived[i].target_type
  }
  return { start_type: startType, hops: derived }
}

/** A chain represents a submittable spec only when every triple validates
 *  against the schema (submission rechecks every triple — DC-14). */
export function buildSpec(
  index: SchemaIndex,
  state: BuilderState,
): { start_type: string; start_filters: JsonObject; hops: { relation: string; direction: BuilderDirection; target_type: string }[] } | null {
  if (state.start_type === null) return null
  let current = state.start_type
  const hops: { relation: string; direction: BuilderDirection; target_type: string }[] = []
  for (const hop of state.hops) {
    if (
      hop.relation === null ||
      hop.direction === null ||
      hop.target_type === null ||
      !index.directionsFor(current, hop.relation).includes(hop.direction) ||
      !index.targetsFor(hop.relation, hop.direction).includes(hop.target_type)
    ) {
      return null
    }
    hops.push({ relation: hop.relation, direction: hop.direction, target_type: hop.target_type })
    current = hop.target_type
  }
  return { start_type: state.start_type, start_filters: {}, hops }
}

/** Parse a /builder/schema response defensively (entity/relation rows only). */
export function schemaFromApi(payload: unknown): Schema {
  const data = (payload && typeof payload === "object" && !Array.isArray(payload)
    ? payload
    : {}) as Record<string, unknown>
  const entityTypes = (Array.isArray(data.entity_types) ? data.entity_types : [])
    .map((entry) => entry as BuilderSchemaEntry)
    .filter((entry) => typeof entry.name === "string")
  const relationTypes = (Array.isArray(data.relation_types) ? data.relation_types : [])
    .map((entry) => entry as Schema["relation_types"][number])
    .filter(
      (entry) =>
        typeof entry.name === "string" &&
        Array.isArray(entry.domain) &&
        Array.isArray(entry.range),
    )
  return { entity_types: entityTypes, relation_types: relationTypes }
}
