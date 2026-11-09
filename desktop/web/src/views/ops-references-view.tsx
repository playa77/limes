// src/views/ops-references-view.tsx
// FR-DC-052: sources and ontology metadata as reference panels — the source
// registry, the entity/relation type catalog with domain/range, and ontology
// versions. Everything is data from GET /sources, /ontology, /ontology/versions.

import { useMemo } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import type { SourceInfo } from "@/api/types"
import { DataTable } from "@/components/data-table"
import { DataGridColumnHeader } from "@/components/reui/data-grid/data-grid-column-header"
import type { DataGridFeatures } from "@/components/reui/data-grid/data-grid"
import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/reui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

interface OntologyEntry {
  name: string
  supertype?: string | null
  domain?: string[]
  range?: string[]
}

export function ReferencesView() {
  const sources = useQuery({
    queryKey: ["api", "sources"],
    queryFn: () => apiClient.sources(),
    staleTime: 60_000,
  })
  const ontology = useQuery({
    queryKey: ["api", "ontology"],
    queryFn: () => apiClient.ontology(),
    staleTime: Infinity,
  })
  const versions = useQuery({
    queryKey: ["api", "ontology", "versions"],
    queryFn: () => apiClient.ontologyVersions(),
    staleTime: Infinity,
  })

  return (
    <ViewPage>
      <PageHeader
        title="Sources & ontology"
        description="Reference panels over the API's registry and type catalog"
      />
      <Tabs defaultValue="sources">
        <TabsList>
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="ontology">Ontology</TabsTrigger>
          <TabsTrigger value="versions">Versions</TabsTrigger>
        </TabsList>

        <TabsContent value="sources">
          <Region spacing="sm" dense>
            {sources.isPending ? <RegionSkeleton rows={4} /> : null}
            {sources.isError ? (
              <RegionError detail={sources.error.message} onRetry={() => void sources.refetch()} />
            ) : null}
            <SourcesTable data={sources.data ?? []} />
          </Region>
        </TabsContent>

        <TabsContent value="ontology">
          <Region spacing="sm" dense>
            {ontology.isPending ? <RegionSkeleton rows={4} /> : null}
            {ontology.isError ? (
              <RegionError detail={ontology.error.message} onRetry={() => void ontology.refetch()} />
            ) : null}
            {ontology.data ? <OntologyTable data={ontology.data} /> : null}
          </Region>
        </TabsContent>

        <TabsContent value="versions">
          <Region spacing="sm">
            {versions.isPending ? <RegionSkeleton rows={2} /> : null}
            {versions.isError ? (
              <RegionError detail={versions.error.message} onRetry={() => void versions.refetch()} />
            ) : null}
            <div className="flex flex-wrap gap-1.5">
              {(versions.data ?? []).map((version) => (
                <Badge key={version} variant="outline">
                  {version}
                </Badge>
              ))}
              {versions.data && versions.data.length === 0 ? (
                <EmptyNote>No recorded ontology versions beyond the current one.</EmptyNote>
              ) : null}
            </div>
          </Region>
        </TabsContent>
      </Tabs>
    </ViewPage>
  )
}

function SourcesTable({ data }: { data: SourceInfo[] }) {
  const columns = useMemo<ColumnDef<DataGridFeatures, SourceInfo>[]>(
    () => [
      {
        accessorKey: "source_id",
        id: "source_id",
        header: ({ column }) => <DataGridColumnHeader title="Source" column={column} />,
        cell: ({ row }) => <span className="text-xs font-medium">{row.original.source_id}</span>,
        meta: { headerClassName: "", cellClassName: "" },
        size: 140,
      },
      {
        accessorKey: "name",
        id: "name",
        header: ({ column }) => <DataGridColumnHeader title="Name" column={column} />,
        cell: ({ row }) => <span className="text-xs">{row.original.name}</span>,
        size: 200,
      },
      {
        accessorKey: "kind",
        id: "kind",
        header: ({ column }) => <DataGridColumnHeader title="Kind" column={column} />,
        cell: ({ row }) => <Badge variant="outline">{row.original.kind}</Badge>,
        size: 120,
      },
      {
        accessorKey: "trust_rank",
        id: "trust",
        header: ({ column }) => <DataGridColumnHeader title="Trust" column={column} />,
        cell: ({ row }) => (
          <span className="text-xs tabular-nums">{row.original.trust_rank.toFixed(2)}</span>
        ),
        meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
        size: 90,
      },
      {
        accessorKey: "supports_backfill",
        id: "backfill",
        header: ({ column }) => <DataGridColumnHeader title="Backfill" column={column} />,
        cell: ({ row }) => <Badge variant={row.original.supports_backfill ? "success-light" : "outline"}>{String(row.original.supports_backfill)}</Badge>,
        size: 100,
      },
      {
        accessorKey: "supports_incremental",
        id: "incremental",
        header: ({ column }) => <DataGridColumnHeader title="Incremental" column={column} />,
        cell: ({ row }) => <Badge variant={row.original.supports_incremental ? "success-light" : "outline"}>{String(row.original.supports_incremental)}</Badge>,
        size: 110,
      },
      {
        accessorKey: "last_success_at",
        id: "success",
        header: ({ column }) => <DataGridColumnHeader title="Last success" column={column} />,
        cell: ({ row }) => (
          <span className="text-xs tabular-nums">{row.original.last_success_at ?? "never"}</span>
        ),
        size: 170,
      },
    ],
    [],
  )
  if (data.length === 0) return <EmptyNote>No registered sources.</EmptyNote>
  return <DataTable data={data} columns={columns} pageSize={12} getRowId={(row) => row.source_id} />
}

function OntologyTable({ data }: { data: Record<string, unknown> }) {
  const entityTypes = Array.isArray(data.entity_types) ? (data.entity_types as OntologyEntry[]) : []
  const relationTypes = Array.isArray(data.relation_types)
    ? (data.relation_types as OntologyEntry[])
    : []
  return (
    <div className="flex flex-col gap-4">
      <section aria-label="Entity types">
        <p className="mb-1 text-xs font-semibold">Entity types</p>
        <div className="flex flex-wrap gap-1.5">
          {entityTypes.map((entry) => (
            <Badge key={entry.name} variant="primary-light">
              {entry.name}
              {entry.supertype ? ` ⊂ ${entry.supertype}` : ""}
            </Badge>
          ))}
        </div>
      </section>
      <section aria-label="Relation types">
        <p className="mb-1 text-xs font-semibold">Relation types (domain → range)</p>
        <ul className="flex flex-col">
          {relationTypes.map((entry) => (
            <li
              key={entry.name}
              className="border-border/60 grid grid-cols-[minmax(0,1fr)] gap-1 border-b py-1.5 last:border-b-0"
            >
              <span className="text-xs font-medium">{entry.name}</span>
              <span className="text-muted-foreground text-xs">
                {(entry.domain ?? []).join(", ")} → {(entry.range ?? []).join(", ")}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
