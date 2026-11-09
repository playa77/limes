// src/views/entity-view.tsx
// FR-DC-020/021/022/023 + AC-DC-2: bitemporal property rendering, per-
// assertion provenance one click away, ontology-filtered neighborhood with
// re-centering, enrichment snapshots, and assertion evidence navigation.

import { useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError } from "@/api/errors"
import { useSession } from "@/state/session"
import { PageHeader, Region, RegionError, RegionSkeleton, EmptyNote, ViewPage } from "@/components/page-shell"
import { Badge } from "@/components/reui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { EntityRef, NeighborRow } from "@/api/types"

const _VALIDITY_LABELS: Record<string, string> = {
  valid_from: "VALIDITY",
  valid_to: "VALIDITY (to)",
  recorded_at: "BELIEF",
}

export function EntityView() {
  const { entityId = "" } = useParams()
  const navigate = useNavigate()
  const setSelection = useSession((s) => s.setSelection)

  useEffect(() => {
    if (entityId) setSelection(entityId)
  }, [entityId, setSelection])

  const detail = useQuery({
    queryKey: ["api", "entity", entityId],
    queryFn: () => apiClient.entity(entityId),
    enabled: entityId !== "",
    retry: 1,
  })

  if (entityId === "") {
    return (
      <ViewPage>
        <PageHeader title="Entity" description="No entity selected" />
        <Region>
          <EmptyNote>
            Open an entity from search, the network, or a claim to inspect it here.
          </EmptyNote>
        </Region>
      </ViewPage>
    )
  }

  if (detail.isPending || detail.isFetching) {
    return (
      <ViewPage>
        <PageHeader title="Entity" description="Loading entity…" />
        <Region title="Properties">
          <RegionSkeleton rows={5} />
        </Region>
      </ViewPage>
    )
  }

  if (detail.isError || detail.data === undefined) {
    return (
      <ViewPage>
        <PageHeader title="Entity" description={`Could not load ${entityId}`} />
        <Region>
          <RegionError
            detail={
              detail.error instanceof ApiError
                ? `API error ${detail.error.status}: ${detail.error.detail}`
                : "API transport unavailable."
            }
            onRetry={() => void detail.refetch()}
          />
        </Region>
      </ViewPage>
    )
  }

  const entity = detail.data.entity
  return (
    <ViewPage>
      <PageHeader
        title={entity.label}
        description={entity.entity_id}
        actions={
          <>
            <Badge variant="primary-light">{entity.type}</Badge>
            {entity.ontology_version ? (
              <Badge variant="outline">{entity.ontology_version}</Badge>
            ) : null}
          </>
        }
      />
      <Tabs defaultValue="properties">
        <TabsList>
          <TabsTrigger value="properties">Properties</TabsTrigger>
          <TabsTrigger value="assertions">Assertions</TabsTrigger>
          <TabsTrigger value="neighbors">Neighbors</TabsTrigger>
          <TabsTrigger value="enrichment">Enrichment</TabsTrigger>
        </TabsList>
        <TabsContent value="properties">
          <Region spacing="sm">
            <PropertyTable entity={entity} />
          </Region>
        </TabsContent>
        <TabsContent value="assertions">
          <AssertionsTab entityId={entityId} />
        </TabsContent>
        <TabsContent value="neighbors">
          <NeighborsTab
            entityId={entityId}
            onRecenter={(id) => {
              setSelection(id)
              navigate(`/entity/${encodeURIComponent(id)}`)
            }}
          />
        </TabsContent>
        <TabsContent value="enrichment">
          <EnrichmentTab entityId={entityId} />
        </TabsContent>
      </Tabs>
      <p className="text-muted-foreground text-xs">
        <Link to="/search" className="underline">
          Back to search
        </Link>
      </p>
    </ViewPage>
  )
}

function PropertyTable({ entity }: { entity: EntityRef }) {
  const entries = useMemo(
    () => Object.entries(entity.properties).sort(([a], [b]) => a.localeCompare(b)),
    [entity.properties],
  )
  const temporal = (name: string, value: string, kind: "validity" | "belief") => (
    <div key={`${name}::${value}::${kind}`} className="flex items-center gap-2 py-0.5">
      <Badge variant={kind === "validity" ? "success-light" : "info-light"}>
        {kind === "validity" ? name : "BELIEF"}
      </Badge>
      <code className="text-xs">{value}</code>
    </div>
  )
  return (
    <dl className="flex flex-col">
      {entries.length === 0 ? (
        <EmptyNote>This entity carries no properties beyond its identifier.</EmptyNote>
      ) : null}
      {entries.map(([name, value]) => {
        const rendered =
          typeof value === "string" || typeof value === "number" || typeof value === "boolean"
            ? String(value)
            : JSON.stringify(value)
        if (name === "valid_from" && typeof value === "string")
          return temporal(name, rendered, "validity")
        if (name === "valid_to" && typeof value === "string")
          return temporal(name, rendered, "validity")
        if (name === "recorded_at" && typeof value === "string") {
          // Bitemporal display is a first-class concern (AC-DC-2): belief time
          // wears its own badge so the two time axes never collapse.
          return temporal(name, rendered, "belief")
        }
        return (
          <div key={name} className="border-border/60 grid grid-cols-[minmax(8rem,14rem),minmax(0,1fr)] gap-2 border-b py-1 last:border-b-0">
            <dt className="text-xs font-medium break-words">{_VALIDITY_LABELS[name] ?? name}</dt>
            <dd className="text-xs break-words">
              {rendered === "" ? <span className="text-muted-foreground">(empty)</span> : rendered}
            </dd>
          </div>
        )
      })}
      {entity.created_at ? (
        <div className="border-border/60 mt-1 grid grid-cols-[minmax(8rem,14rem),minmax(0,1fr)] gap-2 border-b py-1 last:border-b-0">
          <dt className="text-xs font-medium">created</dt>
          <dd className="text-muted-foreground text-xs">{entity.created_at}</dd>
        </div>
      ) : null}
    </dl>
  )
}

function AssertionsTab({ entityId }: { entityId: string }) {
  const [selected, setSelected] = useState<NeighborRow | null>(null)
  const detail = useQuery({
    queryKey: ["api", "entity", entityId],
    queryFn: () => apiClient.entity(entityId),
  })
  const neighbors = useQuery({
    queryKey: ["api", "entity", entityId, "neighbors", ""],
    queryFn: () => apiClient.entityNeighbors(entityId),
  })
  const rows = (neighbors.data?.neighbors ?? []).slice(0, 200)

  return (
    <Region spacing="sm" title="Assertions" description="One row per assertion edge; provenance is one click away.">
      {neighbors.isPending ? <RegionSkeleton rows={4} /> : null}
      {neighbors.isError ? (
        <RegionError
          detail={neighbors.error instanceof ApiError ? neighbors.error.detail : "Neighborhood unavailable."}
          onRetry={() => void neighbors.refetch()}
        />
      ) : null}
      <ul className="flex flex-col gap-1">
        {rows.map((row, index) => {
          const confidence =
            row.edge.confidence === null ? "n/a" : row.edge.confidence.toFixed(2)
          return (
            <li key={`${row.edge.assertion_id ?? ""}:${row.neighbor.entity_id}:${index}`}>
              <button
                type="button"
                className={cn(
                  "hover:bg-muted flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors duration-200",
                  selected === row && "bg-muted",
                )}
                onClick={() => setSelected(row)}
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{row.edge.relation}</span>
                  {" → "}
                  <span className="text-muted-foreground">{row.neighbor.label}</span>
                </span>
                <Badge variant="outline">confidence {confidence}</Badge>
              </button>
            </li>
          )
        })}
        {rows.length === 0 && neighbors.isSuccess ? (
          <EmptyNote>No neighboring assertions were returned.</EmptyNote>
        ) : null}
      </ul>
      {selected ? <ProvenancePanel row={selected} /> : null}
      {selected?.edge.assertion_id ? <AssertionEvidence assertionId={selected.edge.assertion_id} /> : null}
      {detail.data ? (
        <dl className="mt-2">
          {Object.entries(detail.data.edge_summary)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([direction, counts]) => (
              <div key={direction} className="flex gap-2 py-0.5 text-xs">
                <dt className="font-medium">{direction}</dt>
                <dd className="text-muted-foreground tabular-nums">
                  {Object.entries(counts)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([relation, count]) => `${relation} ${count}`)
                    .join(", ")}
                </dd>
              </div>
            ))}
        </dl>
      ) : null}
    </Region>
  )
}

const PROVENANCE_HEADINGS = [
  "Provenance",
]

function ProvenancePanel({ row }: { row: NeighborRow }) {
  const edge = row.edge
  const sentence = useSentence(edge)
  const lines: [string, string][] = [
    ["source", edge.source_id ?? "unknown"],
    ["confidence", edge.confidence === null ? "n/a" : String(edge.confidence)],
    ["assertion id", edge.assertion_id ?? "n/a"],
    ["validity", `${edge.valid_from ?? "?"} → ${edge.valid_to ?? "open"}`],
    ["belief (recorded at)", edge.recorded_at ?? "?"],
    ["evidence document", edge.evidence_document_id ?? "none"],
  ]
  if (edge.validity_basis) lines.push(["time basis", edge.validity_basis])
  if (edge.roster_snapshot_id) lines.push(["roster observation", edge.roster_snapshot_id])
  if (edge.extractor_model) lines.push(["extractor model", edge.extractor_model])
  if (edge.prompt_version) lines.push(["prompt version", edge.prompt_version])
  if (edge.schema_version) lines.push(["schema version", edge.schema_version])
  if (edge.source_url) lines.push(["source url", edge.source_url])
  if (edge.report_url) lines.push(["report url", edge.report_url])
  return (
    <div className="border-border rounded-lg border p-3" data-testid="provenance-panel">
      <p className="mb-1 text-xs font-semibold">{PROVENANCE_HEADINGS[0]}</p>
      <dl className="text-xs">
        {lines.map(([name, value]) => (
          <div key={name} className="grid grid-cols-[minmax(7rem,10rem),minmax(0,1fr)] gap-2 py-0.5">
            <dt className="text-muted-foreground">{name}</dt>
            <dd className="break-words">{value}</dd>
          </div>
        ))}
        <div className="grid grid-cols-[minmax(7rem,10rem),minmax(0,1fr)] gap-2 py-0.5">
          <dt className="text-muted-foreground">source sentence</dt>
          <dd className="break-words">
            {sentence.data !== undefined && sentence.data !== null ? (
              <>“{sentence.data}”</>
            ) : edge.evidence_document_id ? (
              sentence.isFetching ? (
                "reading evidence…"
              ) : (
                <>
                  unavailable{" "}
                  <span className="text-muted-foreground">(document not reachable)</span>
                </>
              )
            ) : (
              <span className="text-muted-foreground">none</span>
            )}
          </dd>
        </div>
      </dl>
    </div>
  )
}

function useSentence(edge: NeighborRow["edge"]) {
  const documentId = edge.evidence_document_id
  const start = edge.evidence_start
  const end = edge.evidence_end
  return useQuery({
    queryKey: ["evidence-sentence", documentId, start, end],
    enabled: Boolean(documentId) && typeof start === "number" && typeof end === "number",
    retry: false,
    staleTime: Infinity,
    queryFn: async () => {
      if (!documentId || typeof start !== "number" || typeof end !== "number") return null
      try {
        const document = await apiClient.entity(documentId)
        const body = document.entity.properties.body
        if (typeof body !== "string") return null
        return body.slice(start, end)
      } catch {
        return null
      }
    },
  })
}

function AssertionEvidence({ assertionId }: { assertionId: string }) {
  const navigate = useNavigate()
  const evidence = useQuery({
    queryKey: ["api", "news", "assertion-evidence", assertionId],
    queryFn: () => apiClient.assertionEvidence(assertionId),
    retry: false,
    throwOnError: false,
  })
  if (evidence.isPending) return null
  if (evidence.isError) return null
  if (!evidence.data || Object.keys(evidence.data).length === 0) return null
  return (
    <div className="border-border mt-2 rounded-lg border p-3">
      <p className="mb-1 text-xs font-semibold">Evidence for this assertion</p>
      <pre className="text-muted-foreground max-h-48 overflow-auto text-xs">
        {JSON.stringify(evidence.data, null, 2)}
      </pre>
      <Button
        size="xs"
        variant="outline"
        className="mt-2"
        onClick={() => navigate(`/news/documents/${encodeURIComponent(assertionId)}`)}
      >
        Open document view
      </Button>
    </div>
  )
}

function NeighborsTab({
  entityId,
  onRecenter,
}: {
  entityId: string
  onRecenter: (id: string) => void
}) {
  const [relation, setRelation] = useState<string>("(all relations)")
  const neighbors = useQuery({
    queryKey: ["api", "entity", entityId, "neighbors", ""],
    queryFn: () => apiClient.entityNeighbors(entityId),
  })
  const allRows = neighbors.data?.neighbors ?? []
  const rows =
    relation === "(all relations)"
      ? allRows
      : allRows.filter((row) => row.edge.relation === relation)

  return (
    <Region
      spacing="sm"
      title="Neighbors"
      description="Click a neighbor to re-center; the search history keeps your trail."
      actions={
        <RelationFilter
          rows={allRows}
          value={relation}
          onChange={(next) => setRelation(next)}
        />
      }
    >
      {neighbors.isPending ? <RegionSkeleton rows={4} /> : null}
      {neighbors.isError ? (
        <RegionError
          detail={neighbors.error instanceof ApiError ? neighbors.error.detail : "Neighborhood unavailable."}
          onRetry={() => void neighbors.refetch()}
        />
      ) : null}
      {rows.length === 0 && neighbors.isSuccess ? (
        <EmptyNote>No neighbors across the retained result.</EmptyNote>
      ) : null}
      <ul className="flex flex-col">
        {rows.slice(0, 400).map((row, index) => (
          <li key={`${row.edge.relation}:${row.neighbor.entity_id}:${index}`} className="border-border/60 grid grid-cols-[minmax(0,1fr),minmax(0,1fr),auto] items-center gap-2 border-b px-1 py-1.5 last:border-b-0">
            <button
              type="button"
              className="hover:text-primary truncate text-left text-xs font-medium underline-offset-4 hover:underline"
              onClick={() => onRecenter(row.neighbor.entity_id)}
            >
              {row.neighbor.label}
            </button>
            <span className="text-muted-foreground truncate text-xs">{row.edge.relation}</span>
            <Badge variant="outline">{row.neighbor.type}</Badge>
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-2 text-xs">
        Re-entering an entity keeps the session history (FR-DC-022); the Network pane shares the
        selection state.
      </p>
    </Region>
  )
}

function RelationFilter({
  rows,
  value,
  onChange,
}: {
  rows: NeighborRow[]
  value: string
  onChange: (value: string) => void
}) {
  const relations = useMemo(
    () => [...new Set(rows.map((row) => row.edge.relation))].sort((a, b) => a.localeCompare(b)),
    [rows],
  )
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" className="h-7" aria-label="Filter neighbors by relation">
        <SelectValue placeholder="Filter relation" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="(all relations)">(all relations)</SelectItem>
        {relations.map((relation) => (
          <SelectItem key={relation} value={relation}>
            {relation}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}

function EnrichmentTab({ entityId }: { entityId: string }) {
  const enrichment = useQuery({
    queryKey: ["api", "entity", entityId, "enrichment"],
    queryFn: () => apiClient.enrichment(entityId, { limit: "40" }),
    enabled: entityId !== "",
    retry: false,
  })

  return (
    <Region spacing="sm" title="Enrichment" description="Immutable enrichment snapshots per section (BE-46 contract).">
      {enrichment.isPending ? <RegionSkeleton rows={3} /> : null}
      {enrichment.isError ? (
        <RegionError
          detail={
            enrichment.error instanceof ApiError
              ? enrichment.error.detail
              : "Enrichment unavailable — mirror the API response when this appears."
          }
          onRetry={() => void enrichment.refetch()}
        />
      ) : null}
      {enrichment.data ? (
        <>
          {enrichment.data.diagnosis.length > 0 ? (
            <p className="text-muted-foreground mb-2 text-xs break-words">
              {enrichment.data.diagnosis.join(" ")}
            </p>
          ) : null}
          <ul className="flex flex-col gap-2">
            {enrichment.data.snapshots.map((snapshot, index) => (
              <li key={index} className="border-border rounded-lg border p-2">
                <div className="text-muted-foreground mb-1 flex flex-wrap gap-2 text-xs">
                  <Badge variant="outline">{String(snapshot.section ?? "snapshot")}</Badge>
                  {snapshot.revision !== undefined ? (
                    <Badge variant="outline">revision {String(snapshot.revision)}</Badge>
                  ) : null}
                  {snapshot.attribution ? (
                    <Badge variant="outline">{String(snapshot.attribution)}</Badge>
                  ) : null}
                  {snapshot.license ? (
                    <Badge variant="outline">{String(snapshot.license)}</Badge>
                  ) : null}
                </div>
                <pre className="max-h-40 overflow-auto text-xs" data-testid="snapshot-payload">
                  {JSON.stringify(snapshot, null, 2)}
                </pre>
              </li>
            ))}
          </ul>
          {enrichment.data.truncated ? (
            <EmptyNote>Response truncated by the API limits; narrow with a section filter.</EmptyNote>
          ) : null}
        </>
      ) : null}
    </Region>
  )
}

