// src/components/query-results.tsx
// The shared result surface for every query surface (FR-DC-034/040/043):
// one bundle → network/map/timeline tabs over shared selection state, plus
// the coverage block with the hop-level diagnosis empty state (AC-DC-3).

import { useNavigate } from "react-router"
import { CoveragePanel } from "@/components/coverage-panel"
import { MapPane, NetworkPane, TimelinePane, type BundleLike } from "@/components/graph-panes"
import { TemporalToolbar } from "@/components/temporal-toolbar"
import { Badge } from "@/components/reui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { useSession, type Bundle } from "@/state/session"
import { CodeBlock } from "@/components/reui/code-block/code-block"

export function QueryResultSurface({
  bundle,
  extraHeader,
}: {
  bundle: Bundle | null
  extraHeader?: React.ReactNode
}) {
  const selection = useSession((s) => s.selection)
  const navigate = useNavigate()
  if (bundle === null) return null

  const graph = bundle.outcome.results
  const emptyGraph =
    graph !== null && graph.nodes.length === 0 && graph.edges.length === 0
  const bundleLike: BundleLike | null = graph === null ? null : { result: graph, coverage: bundle.outcome.coverage }

  return (
    <div className="flex flex-col gap-4">
      {bundle?.nlq !== null ? <NlqOutcomePanel bundle={bundle} /> : null}
      {bundle.cypher ? (
        <CodeBlock code={bundle.cypher} language="cypher" variant="ghost" maxLines={18} />
      ) : null}
      {extraHeader}
      {bundleLike !== null ? (
        <>
          <TemporalToolbar />
          <Tabs defaultValue="network">
            <TabsList>
              <TabsTrigger value="network">Network</TabsTrigger>
              <TabsTrigger value="map">Map</TabsTrigger>
              <TabsTrigger value="timeline">Timeline</TabsTrigger>
            </TabsList>
            <TabsContent value="network">
              <NetworkPane bundle={bundleLike} />
            </TabsContent>
            <TabsContent value="map">
              <MapPane bundle={bundleLike} />
            </TabsContent>
            <TabsContent value="timeline">
              <TimelinePane bundle={bundleLike} />
            </TabsContent>
          </Tabs>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline">{graph?.edges.length ?? 0} assertions</Badge>
            <Badge variant="outline">{graph?.nodes.length ?? 0} entities</Badge>
            <Badge variant="outline">source: {bundle.source}</Badge>
            {selection !== null ? (
              <Button size="xs" variant="outline" onClick={() => navigate(`/entity/${encodeURIComponent(selection)}`)}>
                Open selected entity
              </Button>
            ) : null}
          </div>
        </>
      ) : (
        <p className="text-muted-foreground text-xs">
          This outcome did not execute a read query, so there is no graph to render.
        </p>
      )}
      <CoveragePanel
        empty={bundleLike === null || emptyGraph}
        diagnosis={bundle.outcome.diagnosis}
        coverage={bundle.outcome.coverage}
      />
    </div>
  )
}

function NlqOutcomePanel({ bundle }: { bundle: Bundle }) {
  const nlq = bundle.nlq
  if (nlq === null) return null
  return (
    <div className="flex flex-col gap-1 text-xs">
      <p className="text-sm font-medium">{nlq.question}</p>
      {nlq.notes.map((note) => (
        <p key={note} className="text-muted-foreground">
          {note}
        </p>
      ))}
      {nlq.validation_errors.length > 0 ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-2" role="alert">
          <p className="text-destructive-foreground font-medium">Validation failed</p>
          <ul className="text-destructive-foreground list-inside list-disc">
            {nlq.validation_errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {nlq.plan_rejection !== null ? (
        <pre
          className="max-h-40 overflow-auto rounded-md border p-2"
          role="alert"
          aria-label="Plan rejection"
        >
          {JSON.stringify(nlq.plan_rejection, null, 2)}
        </pre>
      ) : null}
    </div>
  )
}
