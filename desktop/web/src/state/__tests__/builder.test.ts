// src/state/__tests__/builder.test.ts
// Pure-module behavior pins for the builder state machine (DC-14 refill
// rules): relation change refills directions, direction change keeps the
// relation, inadmissible selections drop to the first schema option (or to
// null when none exists), downstream suffixes recompute, and submission
// revalidates every triple.

import { describe, expect, it } from "vitest"

import { buildSpec, createIndex, refreshFrom, schemaFromApi, type BuilderState, type Schema } from "../builder"

const SCHEMA: Schema = {
  entity_types: [
    { name: "AardvarkSong", supertype: null },
    { name: "BlueCrayon", supertype: "AardvarkSong" },
    { name: "CopperFeather", supertype: null },
    { name: "DeltaTorch", supertype: null },
  ],
  relation_types: [
    { name: "PURPLE_LADDER", domain: ["AardvarkSong"], range: ["CopperFeather"] },
    { name: "SILVER_LADDER", domain: ["CopperFeather"], range: ["AardvarkSong"] },
  ],
}

const index = createIndex(SCHEMA)

describe("SchemaIndex derivation", () => {
  it("expands supertypes when computing admissible endpoint types", () => {
    expect(index.targetsFor("PURPLE_LADDER", "out")).toEqual(["CopperFeather"])
    // BlueCrayon is concrete with supertype AardvarkSong ⇒ admitted on the domain side.
    expect(index.targetsFor("PURPLE_LADDER", "in")).toEqual(["AardvarkSong", "BlueCrayon"])
    expect(index.directionsFor("BlueCrayon", "PURPLE_LADDER")).toEqual(["out"])
    expect(index.directionsFor("BlueCrayon", "SILVER_LADDER")).toEqual(["in"])
    // CopperFeather sits on PURPLE_LADDER's range and SILVER_LADDER's domain.
    expect(index.directionsFor("CopperFeather", "SILVER_LADDER")).toEqual(["out"])
    expect(index.directionsFor("CopperFeather", "PURPLE_LADDER")).toEqual(["in"])
  })

  it("lists exactly the type-admissible relations in schema order", () => {
    expect(index.relationsFor("AardvarkSong")).toEqual(["PURPLE_LADDER", "SILVER_LADDER"])
    expect(index.relationsFor("BlueCrayon")).toEqual(["PURPLE_LADDER", "SILVER_LADDER"])
    expect(index.relationsFor("CopperFeather")).toEqual(["PURPLE_LADDER", "SILVER_LADDER"])
    expect(index.relationsFor("DeltaTorch")).toEqual([])
    expect(index.relationsFor("Unregistered")).toEqual([])
  })
})

describe("DC-14 refill semantics", () => {
  it("keeps a triple that is still fully admissible", () => {
    const refilled = refreshFrom(
      index,
      "BlueCrayon",
      [{ relation: "PURPLE_LADDER", direction: "out", target_type: "CopperFeather" }],
      0,
      [false],
    )
    expect(refilled.hops[0]).toMatchObject({
      relation: "PURPLE_LADDER",
      direction: "out",
      target_type: "CopperFeather",
    })
  })

  it("an inadmissible direction falls back without touching the relation", () => {
    const refilled = refreshFrom(
      index,
      "BlueCrayon",
      [{ relation: "SILVER_LADDER", direction: "out", target_type: "CopperFeather" }],
      0,
      [true],
    )
    // SILVER_LADDER stays admissible (relation refill retains it); only the
    // direction is invalid for BlueCrayon → the only remaining option is "in".
    expect(refilled.hops[0].relation).toBe("SILVER_LADDER")
    expect(refilled.hops[0].direction).toBe("in")
    expect(refilled.hops[0].target_type).toBe("CopperFeather")
  })

  it("an inadmissible target falls back to the first schema option", () => {
    const refilled = refreshFrom(
      index,
      "BlueCrayon",
      [{ relation: "PURPLE_LADDER", direction: "out", target_type: "AardvarkSong" }],
      0,
      [false],
    )
    expect(refilled.hops[0]).toMatchObject({
      relation: "PURPLE_LADDER",
      direction: "out",
      target_type: "CopperFeather",
    })
  })

  it("a downstream suffix recomputes from the actor hop's derived target", () => {
    const refilled = refreshFrom(
      index,
      "CopperFeather",
      [
        { relation: "PURPLE_LADDER", direction: "out", target_type: "CopperFeather" },
        { relation: "SILVER_LADDER", direction: "in", target_type: "AardvarkSong" },
      ],
      1,
    )
    // Hop 0 is before the actor and passes through untouched.
    expect(refilled.hops[0]).toMatchObject({
      relation: "PURPLE_LADDER",
      direction: "out",
      target_type: "CopperFeather",
    })
    // Hop 1 recomputes against target_of(hop 0) = CopperFeather: SILVER_LADDER retains,
    // direction "in" is inadmissible for CopperFeather ⇒ falls to "out".
    expect(refilled.hops[1]).toMatchObject({
      relation: "SILVER_LADDER",
      direction: "out",
      target_type: "AardvarkSong",
    })
  })

  it("a type with no admissible relations empty-picks everything", () => {
    const refilled = refreshFrom(
      index,
      "DeltaTorch",
      [{ relation: "PURPLE_LADDER", direction: "out", target_type: "CopperFeather" }],
      0,
      [true],
    )
    expect(refilled.hops[0]).toEqual({
      relation: null,
      direction: null,
      target_type: null,
      relations: [],
      directions: [],
      targets: [],
    })
  })
})

describe("submission revalidation", () => {
  it("builds a valid chain into the wire spec", () => {
    const state = refreshFrom(
      index,
      "BlueCrayon",
      [{ relation: "PURPLE_LADDER", direction: "out", target_type: "CopperFeather" }],
      0,
      [true],
    )
    expect(buildSpec(index, state)).toEqual({
      start_type: "BlueCrayon",
      start_filters: {},
      hops: [{ relation: "PURPLE_LADDER", direction: "out", target_type: "CopperFeather" }],
    })
  })

  it("rejects a chain whose tail triple no longer validates", () => {
    // Handcrafted, unrefilled state: submission rechecks every triple, so a
    // stale/poisoned selection (AardvarkSong cannot be EMPLOYED-OUT target)
    // is refused even if the derivation step would have normalized it.
    const state: BuilderState = {
      start_type: "BlueCrayon",
      hops: [
        {
          relation: "PURPLE_LADDER",
          direction: "out",
          target_type: "AardvarkSong",
          relations: [],
          directions: [],
          targets: [],
        },
      ],
    }
    expect(buildSpec(index, state)).toBeNull()
  })

  it("rejects a chain with an unselected hop", () => {
    expect(
      buildSpec(index, {
        start_type: "BlueCrayon",
        hops: [
          {
            relation: null,
            direction: null,
            target_type: null,
            relations: [],
            directions: [],
            targets: [],
          },
        ],
      }),
    ).toBeNull()
  })
})

describe("schema parsing", () => {
  it("drops malformed schema rows and empty payloads", () => {
    const parsed = schemaFromApi({
      entity_types: [{ name: "AardvarkSong" }, "junk", { name: 42 }],
      relation_types: [
        { name: "PURPLE_LADDER", domain: ["AardvarkSong"], range: ["CopperFeather"] },
        { name: "BAD" },
      ],
    })
    expect(parsed.entity_types).toHaveLength(1)
    expect(parsed.relation_types).toHaveLength(1)
    expect(schemaFromApi(null)).toEqual({ entity_types: [], relation_types: [] })
  })
})
