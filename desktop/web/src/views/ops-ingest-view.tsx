// src/views/ops-ingest-view.tsx
// FR-DC-050: run history, current stage and per-source state. Refreshes
// every 10 s while the view is mounted and stops when it unmounts. The
// ledger is passive usage, not a budget read (FR-DC-051).

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import type { IngestRun, CostEntry } from "@/api/types"
import { DataTable } from "@/components/data-table"
import { DataGridColumnHeader } from "@/components/reui/data-grid/data-grid-column-header"
import type { DataGridFeatures } from "@/components/reui/data-grid/data-grid"
import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/reui/badge"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

export function IngestView() {
  const runs = useQuery({
    queryKey: ["api", "ingest", "status"],
    queryFn: () => apiClient.ingestStatus(),
    // Auto-refresh configurable: 10 s while this view is mounted (FR-DC-050).
    refetchInterval: 10_000,
    refetchIntervalInBackground: false,
    staleTime: 10_000,
  })

  const columns: ColumnDef<DataGridFeatures, IngestRun>[] = [
    {
      accessorKey: "source_id",
      id: "source",
      header: ({ column }) => <DataGridColumnHeader title="Source" column={column} />,
      cell: ({ row }) => <span className="text-xs font-medium">{row.original.source_id}</span>,
      meta: { headerClassName: "", cellClassName: "" },
      size: 130,
    },
    {
      accessorKey: "mode",
      id: "mode",
      header: ({ column }) => <DataGridColumnHeader title="Mode" column={column} />,
      cell: ({ row }) => <Badge variant="outline">{row.original.mode}</Badge>,
      size: 100,
    },
    {
      accessorKey: "started_at",
      id: "start",
      header: ({ column }) => <DataGridColumnHeader title="Started" column={column} />,
      cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.started_at}</span>,
      size: 170,
    },
    {
      accessorKey: "finished_at",
      id: "finish",
      header: ({ column }) => <DataGridColumnHeader title="State / finished" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums" title={row.original.last_error ?? undefined}>
          <Badge variant={row.original.errors || row.original.progress_stale ||
            row.original.state === "rate_limited" || row.original.state === "upstream_failure" ||
            row.original.state === "transport_failure" || row.original.state === "partial"
            ? "warning-light" : "info-light"}>
            {(row.original.state ?? (row.original.finished_at ? "window finished" : "acquiring"))
              .replaceAll("_", " ")}
            {row.original.progress_stale ? "; no recent progress; incomplete" : ""}
          </Badge>
          {row.original.finished_at ? <span> {row.original.finished_at}</span> : null}
        </span>
      ),
      size: 190,
    },
    {
      accessorKey: "records_fetched",
      id: "fetched",
      header: ({ column }) => <DataGridColumnHeader title="Fetched" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
    },
    {
      accessorKey: "nodes_created",
      id: "created",
      header: ({ column }) => <DataGridColumnHeader title="Created" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
    },
    {
      accessorKey: "nodes_matched",
      id: "matched",
      header: ({ column }) => <DataGridColumnHeader title="Matched" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
    },
    {
      accessorKey: "assertions_written",
      id: "written",
      header: ({ column }) => <DataGridColumnHeader title="Assertions" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums">
          {row.original.assertions_written} w / {row.original.assertions_skipped} s /{" "}
          {row.original.assertions_rejected} r
        </span>
      ),
      meta: { headerClassName: "text-end", cellClassName: "text-end" },
      size: 140,
    },
    {
      accessorKey: "documents_gated_out",
      id: "gated",
      header: ({ column }) => <DataGridColumnHeader title="Gated out" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 100,
    },
    {
      accessorKey: "errors",
      id: "errors",
      header: ({ column }) => <DataGridColumnHeader title="Errors" column={column} />,
      cell: ({ row }) =>
        row.original.errors > 0 ? (
          <Badge variant="destructive-light">{row.original.errors}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">0</span>
        ),
      meta: { headerClassName: "text-end", cellClassName: "text-end" },
      size: 80,
    },
    {
      accessorKey: "cost_eur",
      id: "cost",
      header: ({ column }) => <DataGridColumnHeader title="Cost €" column={column} />,
      cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.cost_eur.toFixed(2)}</span>,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
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
  ]

  return (
    <ViewPage>
      <PageHeader
        title="Ingest status"
        description="Run history, current stage and per-source state (10 s refresh while open)"
      />
      <Region spacing="sm" dense>
        {runs.isPending ? <RegionSkeleton rows={5} /> : null}
        {runs.isError ? (
          <RegionError detail={runs.error.message} onRetry={() => void runs.refetch()} />
        ) : null}
        {runs.data && runs.data.length === 0 ? (
          <EmptyNote>No ingest runs recorded yet.</EmptyNote>
        ) : null}
        {runs.data && runs.data.length > 0 ? (
          <DataTable data={runs.data} columns={columns} pageSize={12} getRowId={(row) => row.run_id} />
        ) : null}
      </Region>
      <p className="text-muted-foreground text-xs">
        Automatic refresh pauses while the view is unmounted; the passive cost ledger is read-only.
      </p>
    </ViewPage>
  )
}

export function LedgerView() {
  const [period, setPeriod] = useState<string>("")
  const ledger = useQuery({
    queryKey: ["api", "cost", "ledger", period],
    queryFn: () => apiClient.costLedger(period.trim() === "" ? null : period.trim()),
    staleTime: 30_000,
  })

  const columns: ColumnDef<DataGridFeatures, CostEntry>[] = [
    {
      accessorKey: "period",
      id: "period",
      header: ({ column }) => <DataGridColumnHeader title="Period" column={column} />,
      cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.period}</span>,
      size: 110,
    },
    {
      accessorKey: "purpose",
      id: "purpose",
      header: ({ column }) => <DataGridColumnHeader title="Purpose" column={column} />,
      cell: ({ row }) => <span className="text-xs">{row.original.purpose}</span>,
      size: 150,
    },
    {
      accessorKey: "model_id",
      id: "model",
      header: ({ column }) => <DataGridColumnHeader title="Model" column={column} />,
      cell: ({ row }) => <span className="font-mono text-xs">{row.original.model_id}</span>,
      size: 220,
    },
    {
      accessorKey: "run_id",
      id: "run",
      header: ({ column }) => <DataGridColumnHeader title="Run" column={column} />,
      cell: ({ row }) => (
        <span className="text-muted-foreground font-mono text-xs">{row.original.run_id ?? "—"}</span>
      ),
      size: 150,
    },
    {
      accessorKey: "input_tokens",
      id: "input",
      header: ({ column }) => <DataGridColumnHeader title="Input" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
    },
    {
      accessorKey: "output_tokens",
      id: "output",
      header: ({ column }) => <DataGridColumnHeader title="Output" column={column} />,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 90,
    },
    {
      accessorKey: "cost_eur",
      id: "cost",
      header: ({ column }) => <DataGridColumnHeader title="Cost €" column={column} />,
      cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.cost_eur.toFixed(4)}</span>,
      meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
      size: 100,
    },
    {
      accessorKey: "created_at",
      id: "when",
      header: ({ column }) => <DataGridColumnHeader title="Recorded" column={column} />,
      cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.created_at}</span>,
      size: 170,
    },
  ]

  return (
    <ViewPage>
      <PageHeader
        title="Cost ledger"
        description="Passive provider usage and spend; no budget enforcement"
        actions={
          <input
            aria-label="Ledger period filter"
            value={period}
            onChange={(event) => setPeriod(event.target.value)}
            placeholder="2026-10"
            className="border-input bg-background focus-visible:ring-ring/50 h-7 w-32 rounded-md border px-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2"
          />
        }
      />
      <Region spacing="sm" dense>
        {ledger.isPending ? <RegionSkeleton rows={4} /> : null}
        {ledger.isError ? (
          <RegionError detail={ledger.error.message} onRetry={() => void ledger.refetch()} />
        ) : null}
        {ledger.data ? (
          <>
            <div className="mb-2 flex items-center gap-2">
              <span className="text-xs">
                Period <span className="font-medium">{ledger.data.period}</span>
              </span>
              <Badge variant="primary-light">total {ledger.data.spend_eur.toFixed(2)} €</Badge>
            </div>
            {ledger.data.entries.length === 0 ? (
              <EmptyNote>No entries recorded for this period.</EmptyNote>
            ) : (
              <DataTable
                data={ledger.data.entries}
                columns={columns}
                pageSize={15}
                getRowId={(row) => row.ledger_id}
              />
            )}
          </>
        ) : null}
      </Region>
      <p className="text-muted-foreground text-xs">
        The ledger records provider usage; there is no spend governor or ceiling requirement.
      </p>
    </ViewPage>
  )
}
