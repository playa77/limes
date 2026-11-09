// src/components/graph-panes.tsx
// The three visualization panes rendered from the shared payload builders.
// Cytoscape (network), Leaflet (coordinate-only map, no tiles — OI-11/D-86),
// and Plotly (timeline). Selection stays shared through the session store
// (FR-DC-043); panes never issue queries.

import { useEffect, useMemo, useRef, useState } from "react"
import type { Core as CyCore, EventObject } from "cytoscape"
import L from "leaflet"
import Plotly from "plotly.js-dist-min"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { EmptyNote } from "@/components/page-shell"
import {
  mapPayload,
  networkPayload,
  timelinePayload,
  type MapPayload as MapPayloadData,
  type TimelinePayload as TimelinePayloadData,
} from "@/state/payloads"
import type { GraphResult } from "@/api/types"
import { apiClient } from "@/api/index"
import { useSession } from "@/state/session"
import { bundleWithTemporal } from "@/state/payloads"
import { cn } from "@/lib/utils"

export interface BundleLike {
  result: GraphResult
  coverage: Parameters<typeof networkPayload>[1]
}

// -- network (Cytoscape) ----------------------------------------------------

export function NetworkPane({
  bundle,
  className,
}: {
  bundle: BundleLike
  className?: string
}) {
  const selection = useSession((s) => s.selection)
  const setSelection = useSession((s) => s.setSelection)
  const temporalFilter = useSession((s) => s.temporalFilter)
  const [expanded, setExpanded] = useState<GraphResult | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<CyCore | null>(null)
  const [payload, payloadMeta] = useMemo(() => {
    const { result, coverage } = bundleWithTemporal(bundle.result, bundle.coverage, temporalFilter)
    const meta = expanded
      ? mergeGraphs(result, expanded)
      : { result, coverage }
    return [
      networkPayload(meta.result, meta.coverage),
      meta,
    ] as const
  }, [bundle, temporalFilter, expanded])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    void (async () => {
      const cy = (await import("cytoscape")).default({
        container,
        elements: [
          ...payload.nodes.map((node) => ({
            data: {
              id: node.id,
              label: node.label,
              type: node.type,
            },
            group: "nodes" as const,
          })),
          ...payload.edges.map((edge, index) => ({
            data: {
              id: `${edge.source}->${edge.target}:${edge.relation}:${index}`,
              source: edge.source,
              target: edge.target,
              label: edge.relation,
            },
            group: "edges" as const,
          })),
        ],
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              "text-valign": "center",
              "text-halign": "right",
              "font-size": 10,
              color: "#181430",
              "background-color": "#2207d4",
              "border-color": "#18143080",
              width: 18,
              height: 18,
            },
          },
          {
            selector: "edge",
            style: {
              label: "data(label)",
              "font-size": 8,
              color: "#5d5a73",
              "curve-style": "bezier" as const,
              "line-color": "#a8b9c4",
              "target-arrow-color": "#a8b9c4",
              "target-arrow-shape": "triangle",
              "arrow-scale": 0.8,
              width: 1,
            },
          },
          {
            selector: "node:selected",
            style: {
              "background-color": "#0e7c8c",
              "border-color": "#0e7c8c",
            },
          },
        ],
        layout: { name: "cose", animate: false, padding: 20 },
      })
      cy.on("tap", "node", (event: EventObject) => {
        setSelection(String(event.target.id()))
      })
      cy.on("tap", "edge", (event: EventObject) => {
        const edge = event.target
        const source = String(edge.source().id())
        setSelection(source)
      })
      cyRef.current = cy
    })()
    return () => {
      cyRef.current?.destroy()
      cyRef.current = null
    }
  }, [payload, setSelection])

  // Selection highlight sync (entity panel ↔ network view, FR-DC-043).
  useEffect(() => {
    const cy = cyRef.current
    if (!cy) return
    cy.nodes(":selected").unselect()
    if (selection !== null) {
      const node = cy.getElementById(selection)
      if (node.nonempty()) {
        cy.elements(":unselected").unselect()
        node.select()
      }
    }
  }, [selection, payload])

  async function expand() {
    if (selection === null) return
    try {
      const neighbors = await apiClient.entityNeighbors(selection)
      // Retained expansion (DC-14): prior deltas survive the redraw.
      const merged: GraphResult = {
        nodes: [...(expanded ?? payloadMeta.result).nodes, ...neighbors.neighbors.map((r) => r.neighbor)],
        edges: [...(expanded ?? payloadMeta.result).edges, ...neighbors.neighbors.map((r) => r.edge)],
        counts: { ...(expanded ?? payloadMeta.result).counts },
      }
      setExpanded(merged)
    } catch {
      // Surface through the shared error region (parent view renders errors).
      setExpanded(null)
    }
  }

  return (
    <div className={cn("flex h-[26rem] flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <Badge variant="outline">{payload.nodes.length} nodes</Badge>
        <Badge variant="outline">{payload.edges.length} edges</Badge>
        <span className="text-muted-foreground text-xs">
          {payload.nodes.length === 0 && payload.edges.length === 0 ? "No graph elements." : null}
        </span>
        <Button
          size="xs"
          variant="outline"
          className="ms-auto"
          disabled={selection === null}
          onClick={expand}
        >
          Expand selected
        </Button>
      </div>
      <div className="bg-card min-h-0 flex-1 overflow-hidden rounded-lg border">
        <div ref={containerRef} className="size-full" />
      </div>
      <p className="text-muted-foreground text-xs">
        Click a node to select it; the entity view reflects the same selection.
      </p>
      {payload.nodes.length === 0 ? <EmptyNote>No nodes after the active filters.</EmptyNote> : null}
    </div>
  )
}

function mergeGraphs(
  base: GraphResult,
  extra: GraphResult,
): { result: GraphResult; coverage: NetworkPaneProps["bundle"]["coverage"] } {
  const nodeIds = new Set(base.nodes.map((node) => node.entity_id))
  const edgeKeys = new Set(
    base.edges.map((edge) => `${edge.subject_id}|${edge.relation}|${edge.object_id}|${edge.assertion_id ?? ""}`),
  )
  return {
    result: {
      nodes: [...base.nodes, ...extra.nodes.filter((node) => !nodeIds.has(node.entity_id))],
      edges: [
        ...base.edges,
        ...extra.edges.filter(
          (edge) =>
            !edgeKeys.has(`${edge.subject_id}|${edge.relation}|${edge.object_id}|${edge.assertion_id ?? ""}`),
        ),
      ],
      counts: { ...base.counts },
    },
    coverage: null,
  }
}

interface NetworkPaneProps {
  bundle: BundleLike
  className?: string
}

// -- map (Leaflet, coordinate-only per D-86) --------------------------------

export function MapPane({ bundle, className }: { bundle: BundleLike; className?: string }) {
  const selection = useSession((s) => s.selection)
  const setSelection = useSession((s) => s.setSelection)
  const temporalFilter = useSession((s) => s.temporalFilter)
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<L.Map | null>(null)
  const layerRef = useRef<L.LayerGroup | null>(null)

  const payload: MapPayloadData = useMemo(() => {
    const { result, coverage } = bundleWithTemporal(bundle.result, bundle.coverage, temporalFilter)
    const data = mapPayload(result, coverage, selection)
    return data
  }, [bundle, temporalFilter, selection])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    // The coordinate-only canvas carries no basemap (DC-14/OI-11/OI-18): the
    // API is the only network the client may touch.
    const map = L.map(containerRef.current, {
      center: [51, 10],
      zoom: 4,
      scrollWheelZoom: true,
      attributionControl: false,
    })
    L.svg({ padding: 0.2 }).addTo(map)
    mapRef.current = map
    layerRef.current = L.layerGroup().addTo(map)
    return () => {
      map.remove()
      mapRef.current = null
      layerRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    const layer = layerRef.current
    if (!map || !layer) return
    layer.clearLayers()
    for (const node of payload.nodes) {
      const marker = L.circleMarker(node.geometry, {
        radius: 6,
        color: node.id === selection ? "#0e7c8c" : "#2207d4",
        fillColor: node.id === selection ? "#0e7c8c" : "#2207d4",
        fillOpacity: 0.75,
        weight: 1.5,
      })
      marker.bindTooltip(node.label, { direction: "top" })
      marker.on("click", () => setSelection(node.id))
      layer.addLayer(marker)
    }
    for (const line of payload.lines) {
      layer.addLayer(
        L.polyline(line.points, {
          color: "#2207d4",
          weight: 2,
        }).on("click", () => setSelection(line.source)),
      )
    }
    const points = payload.nodes.map((node) => node.geometry)
    if (points.length > 0) {
      map.fitBounds(L.latLngBounds(points).pad(0.25))
    }
  }, [payload, selection, setSelection])

  return (
    <div className={cn("flex h-[26rem] flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <Badge variant="outline">{payload.nodes.length} geoms</Badge>
        <Badge variant="outline">{payload.lines.length} lines from selection</Badge>
      </div>
      <div
        className="bg-card/70 relative min-h-0 flex-1 overflow-hidden rounded-lg border"
        style={{ ["--leaflet-background" as string]: "#eef0f3" }}
      >
        <div ref={containerRef} className="size-full" />
        <p className="pointer-events-none absolute bottom-1 left-2 text-[10px] text-neutral-600">
          Coordinate-only map: no basemap tiles; deliberate API-only networking.
        </p>
      </div>
      {payload.nodes.length === 0 ? (
        <EmptyNote>
          {payload.missing_geometry > 0
            ? `${payload.missing_geometry} elements without finite geometry are not shown.`
            : "No geometry in the retained result."}
        </EmptyNote>
      ) : null}
    </div>
  )
}

// -- timeline (Plotly) ------------------------------------------------------

export function TimelinePane({ bundle, className }: { bundle: BundleLike; className?: string }) {
  const setSelection = useSession((s) => s.setSelection)
  const temporalFilter = useSession((s) => s.temporalFilter)
  const containerRef = useRef<HTMLDivElement>(null)

  const payload: TimelinePayloadData = useMemo(() => {
    const { result, coverage } = bundleWithTemporal(bundle.result, bundle.coverage, temporalFilter)
    return timelinePayload(result, coverage, temporalFilter.validity_from, temporalFilter.validity_to)
  }, [bundle, temporalFilter])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const validityAxis = {
      x: payload.validity.map((point) => point.t),
      y: payload.validity.map((point) => point.relation),
      text: payload.validity.map(
        (point) => `${point.relation} — ${point.source ?? "?"} → ${point.target ?? "?"}`,
      ),
      customdata: payload.validity.map((point) => [point.source ?? point.target ?? "", point.t]),
      mode: "markers" as const,
      marker: { color: "#2207d4", size: 6 },
      type: "scatter" as const,
      name: "validity time",
    }
    const beliefAxis = {
      x: payload.belief.map((point) => point.t),
      y: payload.belief.map((point) => point.relation),
      text: payload.belief.map(
        (point) =>
          `${point.relation} — recorded ${point.t}${point.event_status ? `, ${point.event_status}` : ""}`,
      ),
      customdata: payload.belief.map((point) => [point.source ?? point.target ?? "", point.t]),
      mode: "markers" as const,
      marker: { color: "#0e7c8c", size: 6 },
      type: "scatter" as const,
      name: "belief (recorded) time",
    }
    const data = [validityAxis, beliefAxis]
    const layout: Partial<Parameters<typeof Plotly.react>[2]> = {
      margin: { l: 20, r: 12, t: 8, b: 28 },
      showlegend: true,
      legend: { orientation: "h", y: 1.12 },
      font: { family: "Inter Variable, sans-serif", size: 10, color: "#5d5a73" },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      xaxis: { type: "date" as const, title: { text: "assertion instant" } },
      yaxis: { automargin: true },
      hovermode: "closest" as const,
    }
    Plotly.react(container, data, layout)
      .then(() => {
        void container
      })
      .catch(() => {})
    const clickHandler: Parameters<typeof container.addEventListener>[1] = (event) => {
      // Plotly emits 'plotly_click' as a custom DOM event with the point.
      const detail = (event as CustomEvent<{ points: { customdata?: string[] }[] }>).detail
      const first = detail?.points[0]
      const sourceId = first?.customdata?.[0]
      if (typeof sourceId === "string") setSelection(sourceId)
    }
    container.addEventListener("plotly_click", clickHandler)
    return () => {
      container.removeEventListener("plotly_click", clickHandler)
      void Plotly.purge(container)
    }
  }, [payload, setSelection])

  return (
    <div className={cn("flex h-[26rem] flex-col gap-2", className)}>
      <div className="flex items-center gap-2">
        <Badge variant="outline">{payload.validity.length} validity points</Badge>
        <Badge variant="outline">{payload.belief.length} belief points</Badge>
      </div>
      <div className="bg-card min-h-0 flex-1 rounded-lg border p-1">
        <div ref={containerRef} className="size-full" />
      </div>
      <p className="text-muted-foreground text-xs">
        Validity and belief markers are separate series; unknown event times appear on the belief
        axis only.
      </p>
    </div>
  )
}
