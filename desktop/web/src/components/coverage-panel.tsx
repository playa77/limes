// src/components/coverage-panel.tsx
// FR-DC-034 / AC-DC-3: the shared coverage block. When the query emptied the
// result set the panel IS the empty state — one row per hop from the API's
// Diagnosis (which hop emptied the set plus the graph-wide relation counts),
// never a bare "no results". Non-empty results show the coverage summary.

import { Fragment } from "react"
import { Frame, FramePanel, FrameHeader, FrameTitle } from "@/components/reui/frame"
import { Badge } from "@/components/reui/badge"
import { cn } from "@/lib/utils"
import type { CoverageReport, Diagnosis } from "@/api/types"

const EMPTY_INTRO = "The query emptied the result set — see the hop diagnosis below."

export function CoveragePanel({
  empty,
  diagnosis,
  coverage,
  className,
}: {
  /** The query returned no nodes/rows and a diagnosis is available. */
  empty: boolean
  diagnosis: Diagnosis | null
  coverage: CoverageReport | null
  className?: string
}) {
  if (empty && diagnosis !== null) {
    return <DiagnosisEmptyState diagnosis={diagnosis} className={className} />
  }
  if (coverage === null || (Object.keys(coverage.relation_counts).length === 0 && coverage.contributing_sources.length === 0)) {
    return null
  }
  return <CoverageSummary coverage={coverage} className={className} />
}

function DiagnosisEmptyState({
  diagnosis,
  className,
}: {
  diagnosis: Diagnosis
  className?: string
}) {
  const entries = Object.entries(diagnosis.relation_counts).sort(([a], [b]) =>
    a.localeCompare(b),
  )
  const note =
    diagnosis.note.length > 0
      ? diagnosis.note
      : `hop ${diagnosis.clause_index} (${diagnosis.failing_clause})`
  return (
    <Frame spacing="sm" className={cn("shadow-lifted-sm", className)}>
      <FramePanel>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Badge variant="warning-light">empty result</Badge>
            <p className="text-foreground text-xs font-medium">{EMPTY_INTRO}</p>
          </div>
          <p className="text-muted-foreground text-xs break-words">{note}</p>
          <table className="text-xs">
            <caption className="sr-only">Hop-level diagnosis with graph-wide counts</caption>
            <thead>
              <tr className="text-muted-foreground border-b">
                <th scope="col" className="px-1 py-1 text-left font-medium">
                  hop
                </th>
                <th scope="col" className="px-1 py-1 text-left font-medium">
                  relation
                </th>
                <th scope="col" className="px-1 py-1 text-right font-medium">
                  graph-wide count
                </th>
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {entries.length === 0 ? null : (
                entries.map(([relation, count]) => {
                  const emptied = relation === diagnosis.failing_clause
                  return (
                    <tr key={relation} className="border-b last:border-b-0">
                      <td className="px-1 py-1">
                        hop {diagnosis.clause_index}
                        {emptied ? " (emptied)" : ""}
                      </td>
                      <td className="px-1 py-1">{relation}</td>
                      <td className="px-1 py-1 text-right">{count}</td>
                    </tr>
                  )
                })
              )}
              {entries.length === 0 ? (
                <tr>
                  <td colSpan={3} className="text-muted-foreground px-1 py-2">
                    {`No relation counts were returned with hop ${diagnosis.clause_index} (${diagnosis.failing_clause}).`}
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </FramePanel>
    </Frame>
  )
}

function CoverageSummary({
  coverage,
  className,
}: {
  coverage: CoverageReport
  className?: string
}) {
  const relations = Object.entries(coverage.relation_counts).sort(([a], [b]) =>
    a.localeCompare(b),
  )
  return (
    <Frame spacing="sm" className={cn("shadow-lifted-sm", className)}>
      <FrameHeader>
        <FrameTitle>coverage</FrameTitle>
      </FrameHeader>
      <FramePanel>
        <dl className="text-xs">
          {relations.map(([relation, count]) => (
            <Fragment key={relation}>
              <div className="flex items-baseline justify-between gap-3 py-0.5">
                <dt className="font-medium break-words">{relation}</dt>
                <dd className="text-muted-foreground tabular-nums">{count}</dd>
              </div>
            </Fragment>
          ))}
          {relations.length === 0 ? (
            <p className="text-muted-foreground py-1">No relation counts reported.</p>
          ) : null}
          {coverage.contributing_sources.length > 0 ? (
            <>
              <div className="mt-2" />
              <dt className="silent sr-only">contributing sources</dt>
              <dd className="flex flex-wrap gap-1.5">
                {coverage.contributing_sources.map((source) => {
                  const refreshed = coverage.source_refresh[source]
                  return (
                    <Badge key={source} variant="outline">
                      {source}: {refreshed ?? "never"}
                    </Badge>
                  )
                })}
              </dd>
            </>
          ) : null}
        </dl>
      </FramePanel>
    </Frame>
  )
}
