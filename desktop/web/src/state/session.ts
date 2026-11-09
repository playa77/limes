// src/state/session.ts
// The zustand port of the retired `limes_desktop.state.SessionState`: one
// store carries the active connection, selection, temporal filter and the
// result history; views never mutate each other — everything flows through
// store actions (the web analogue of the Dash callback graph).

import { create } from "zustand"
import type {
  CoverageReport,
  Diagnosis,
  EntityDetail,
  HealthInfo,
  QueryOutcome,
  SearchHit,
} from "@/api/types"
import { EMPTY_TEMPORAL, type TemporalFilter } from "@/state/temporal"

export interface Profile {
  name: string
  base_url: string
}

/** One published query outcome plus the metadata views need downstream. */
export interface Bundle {
  id: string
  /** When the outcome was published (wall time, session-local). */
  publishedAt: string
  outcome: QueryOutcome
  source: string
  cypher: string | null
  nlq: QueryOutcome["nlq"]
  diagnosis: Diagnosis | null
  /** Entity/search surfaces (non-graph outcomes) keep their own payloads. */
  entity: EntityDetail | null
  hits: SearchHit[] | null
}

export type Reachability = "unknown" | "reachable" | "unreachable"

interface SessionStore {
  // connection
  reachability: Reachability
  health: HealthInfo | null
  capabilities: Record<string, boolean> | null
  errorDetail: string | null
  profiles: Profile[]
  activeProfile: string | null
  tokenRequired: boolean

  // investigation state
  selection: string | null
  temporalFilter: TemporalFilter
  history: Bundle[]
  lastOutcome: Bundle | null

  // actions
  setHealth(info: HealthInfo): void
  setUnreachable(detail: string): void
  setCapabilities(caps: Record<string, boolean>): void
  setProfiles(profiles: Profile[], active: string | null): void
  setTokenRequired(required: boolean): void
  setSelection(entityId: string | null): void
  setTemporalFilter(filter: TemporalFilter): void
  publish(outcome: QueryOutcome, extra?: Pick<Bundle, "entity" | "hits" | "source">): void
}

const HISTORY_MAX = 100

let bundleCounter = 0

export const useSession = create<SessionStore>((setState) => ({
  reachability: "unknown",
  health: null,
  capabilities: null,
  errorDetail: null,
  profiles: [],
  activeProfile: null,
  tokenRequired: false,
  selection: null,
  temporalFilter: { ...EMPTY_TEMPORAL },
  history: [],
  lastOutcome: null,

  setHealth(info) {
    setState({ reachability: "reachable", health: info, errorDetail: null })
  },
  setUnreachable(detail) {
    setState({ reachability: "unreachable", errorDetail: detail })
  },
  setCapabilities(caps) {
    setState({ capabilities: caps })
  },
  setProfiles(profiles, active) {
    setState({ profiles, activeProfile: active })
  },
  setTokenRequired(required) {
    setState({ tokenRequired: required })
  },
  setSelection(entityId) {
    setState({ selection: entityId })
  },
  setTemporalFilter(filter) {
    setState({ temporalFilter: { ...filter } })
  },
  publish(outcome, extra) {
    bundleCounter += 1
    const bundle: Bundle = {
      id: `${bundleCounter}`,
      publishedAt: new Date().toISOString(),
      outcome,
      source: extra?.source ?? outcome.source,
      cypher: outcome.cypher,
      nlq: outcome.nlq,
      diagnosis: outcome.diagnosis,
      entity: extra?.entity ?? null,
      hits: extra?.hits ?? null,
    }
    setState((state) => ({
      lastOutcome: bundle,
      history: [...state.history, bundle].slice(-HISTORY_MAX),
    }))
  },
}))

/** Coverage is the FR-DC-034 carrier: every view reads it off the bundle. */
export function bundleCoverage(bundle: Bundle | null): CoverageReport | null {
  return bundle?.outcome.coverage ?? null
}
