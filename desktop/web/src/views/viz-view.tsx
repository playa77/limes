// src/views/viz-view.tsx
// FR-DC-040/041/043: the standalone network/map/timeline views render the
// last published outcome's graph. They are the same panes the query surface
// composes, sharing selection and the temporal filter with the entity panel.

import { useNavigate } from "react-router"
import { useSession } from "@/state/session"
import { MapPane, NetworkPane, TimelinePane, type BundleLike } from "@/components/graph-panes"
import { TemporalToolbar } from "@/components/temporal-toolbar"
import { CoveragePanel } from "@/components/coverage-panel"
import { EmptyNote, PageHeader, Region, ViewPage } from "@/components/page-shell"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"

function useVizBundle(): { bundle: BundleLike | null; empty: boolean } {
  const lastOutcome = useSession((s) => s.lastOutcome)
  if (lastOutcome === null || lastOutcome.outcome.results === null) {
    return { bundle: null, empty: true }
  }
  const graph = lastOutcome.outcome.results
  return {
    bundle: { result: graph, coverage: lastOutcome.outcome.coverage },
    empty: graph.nodes.length === 0 && graph.edges.length === 0,
  }
}

function VizFrame({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: (bundle: BundleLike) => React.ReactNode
}) {
  const navigate = useNavigate()
  const { bundle, empty } = useVizBundle()
  const lastOutcome = useSession((s) => s.lastOutcome)

  return (
    <ViewPage>
      <PageHeader
        title={title}
        description={description}
        actions={
          <Button size="sm" variant="outline" onClick={() => navigate("/query/nl")}>
            Run a query
          </Button>
        }
      />
      <TemporalToolbar />
      {bundle === null ? (
        <Region>
          <EmptyNote>
            No published outcome yet — run a query (NL, builder, or Cypher console) and its graph
            appears here, with coverage and diagnosis.
          </EmptyNote>
        </Region>
      ) : empty ? (
        <>
          <Region>
            <EmptyNote>
              The retained result is empty; its hop-level diagnosis is shared below.
            </EmptyNote>
          </Region>
          <CoveragePanel
            empty={true}
            diagnosis={lastOutcome?.outcome.diagnosis ?? null}
            coverage={lastOutcome?.outcome.coverage ?? null}
          />
        </>
      ) : (
        <>
          <Region spacing="sm">{children(bundle)}</Region>
          {lastOutcome ? (
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">source: {lastOutcome.source}</Badge>
              <CoveragePanel
                empty={empty}
                diagnosis={lastOutcome.outcome.diagnosis}
                coverage={lastOutcome.outcome.coverage}
              />
            </div>
          ) : null}
        </>
      )}
    </ViewPage>
  )
}

export function NetworkView() {
  return (
    <VizFrame
      title="Network"
      description="Cytoscape view over the retained query graph; expand from a selected node"
    >
      {(bundle) => <NetworkPane bundle={bundle} />}
    </VizFrame>
  )
}

export function MapView() {
  return (
    <VizFrame
      title="Map"
      description="Coordinate-only plot of entities with finite geometry; no basemap tiles"
    >
      {(bundle) => <MapPane bundle={bundle} />}
    </VizFrame>
  )
}

export function TimelineView() {
  return (
    <VizFrame
      title="Timeline"
      description="Assertion instants over validity and belief time, as separate series"
    >
      {(bundle) => <TimelinePane bundle={bundle} />}
    </VizFrame>
  )
}
