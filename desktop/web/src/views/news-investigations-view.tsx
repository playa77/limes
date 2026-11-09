// src/views/news-investigations-view.tsx
// Dispatch investigations: status, schedules and retries. Replay is an
// explicit manual action — interrupted jobs are never automatically repeated
// (repo invariant), and tracking captures an entity id list explicitly.

import { useState } from "react"
import { Link } from "react-router"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { toast } from "sonner"
import { useSession } from "@/state/session"
import type { NewsInvestigation } from "@/api/types"
import { DataTable } from "@/components/data-table"
import { DataGridColumnHeader } from "@/components/reui/data-grid/data-grid-column-header"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { ColumnDef } from "@tanstack/react-table"
import type { DataGridFeatures } from "@/components/reui/data-grid/data-grid"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

function statusVariant(status: NewsInvestigation["status"]) {
  switch (status) {
    case "succeeded":
      return "success-light" as const
    case "failed":
      return "destructive-light" as const
    case "running":
    case "queued":
      return "info-light" as const
    case "paused":
      return "warning-light" as const
    default:
      return "outline" as const
  }
}

export function NewsInvestigationsView() {
  const queryClient = useQueryClient()
  const selection = useSession((s) => s.selection)
  const list = useQuery({
    queryKey: ["api", "news", "investigations"],
    queryFn: () => apiClient.newsInvestigations(),
    staleTime: 10_000,
  })

  const replay = useMutation({
    mutationFn: (key: string) => apiClient.replayNews(key),
    onSuccess: () => {
      toast.success("Replay submitted; observe the status row.")
      void queryClient.invalidateQueries({ queryKey: ["api", "news", "investigations"] })
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : "Replay failed",
        { description: error instanceof Error ? error.message : "" },
      ),
  })
  const track = useMutation({
    mutationFn: (payload: { title: string; entity_ids: string[]; interval_minutes: number }) =>
      apiClient.trackNews({
        investigation_id: payload.title.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        title: payload.title,
        entity_ids: payload.entity_ids,
        interval_minutes: payload.interval_minutes,
        active: true,
      }),
    onSuccess: () => {
      toast.success("Investigation tracked.")
      void queryClient.invalidateQueries({ queryKey: ["api", "news", "investigations"] })
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Tracking failed"),
  })

  const columns: ColumnDef<DataGridFeatures, NewsInvestigation>[] = [
    {
      accessorKey: "title",
      id: "title",
      header: ({ column }) => <DataGridColumnHeader title="Investigation" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs font-medium">{row.original.title}</span>
      ),
      meta: { headerClassName: "", cellClassName: "" },
      size: 240,
    },
    {
      accessorKey: "status",
      id: "status",
      header: ({ column }) => <DataGridColumnHeader title="Status" column={column} />,
      cell: ({ row }) => <Badge variant={statusVariant(row.original.status)}>{row.original.status}</Badge>,
      size: 110,
    },
    {
      accessorKey: "interval_minutes",
      id: "interval",
      header: ({ column }) => <DataGridColumnHeader title="Interval" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums">{row.original.interval_minutes} min</span>
      ),
      size: 90,
    },
    {
      accessorKey: "next_due",
      id: "next",
      header: ({ column }) => <DataGridColumnHeader title="Next due" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums">{row.original.next_due ?? "—"}</span>
      ),
      size: 170,
    },
    {
      accessorKey: "last_success",
      id: "success",
      header: ({ column }) => <DataGridColumnHeader title="Last success" column={column} />,
      cell: ({ row }) => (
        <span className="text-xs tabular-nums">{row.original.last_success ?? "never"}</span>
      ),
      size: 170,
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Button
          size="xs"
          variant="outline"
          disabled={replay.isPending}
          onClick={() => replay.mutate(row.original.investigation_id)}
        >
          Replay
        </Button>
      ),
      size: 90,
    },
  ]

  return (
    <ViewPage>
      <PageHeader
        title="News investigations"
        description="Dispatch dispatches: status, schedule and manual replay only"
        actions={
          <TrackDialog selection={selection ?? undefined} onTrack={(payload) => track.mutate(payload)} />
        }
      />
      <Region spacing="sm" dense>
        {list.isPending ? <RegionSkeleton rows={4} /> : null}
        {list.isError ? (
          <RegionError detail={list.error.message} onRetry={() => void list.refetch()} />
        ) : null}
        {list.data && list.data.length === 0 ? (
          <EmptyNote>No investigations tracked yet.</EmptyNote>
        ) : null}
        {list.data && list.data.length > 0 ? (
          <DataTable
            data={list.data}
            columns={columns}
            pageSize={12}
            getRowId={(row) => row.investigation_id}
          />
        ) : null}
      </Region>
      <p className="text-muted-foreground text-xs">
        Replays are deliberate operator actions; an interrupted observation is retained through the
        job id. Claims of an investigation live in{" "}
        <Link to="/news/claims" className="underline">
          the claims view
        </Link>
        .
      </p>
    </ViewPage>
  )
}

function TrackDialog({
  selection,
  onTrack,
}: {
  selection?: string
  onTrack: (payload: { title: string; entity_ids: string[]; interval_minutes: number }) => void
}) {
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState("Entity watch")
  const [entityIds, setEntityIds] = useState(selection ?? "")
  const [interval, setInterval] = useState("60")

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">Track entity…</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Track an entity investigation</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <Label htmlFor="track-title">Title</Label>
          <Input id="track-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          <Label htmlFor="track-entities">Entity ids (comma-separated)</Label>
          <Input
            id="track-entities"
            value={entityIds}
            onChange={(e) => setEntityIds(e.target.value)}
            className="font-mono text-xs"
          />
          <Label htmlFor="track-interval">Interval (minutes)</Label>
          <Input id="track-interval" value={interval} onChange={(e) => setInterval(e.target.value)} />
        </div>
        <DialogFooter>
          <Button
            size="sm"
            type="button"
            disabled={title.trim() === "" || entityIds.trim() === ""}
            onClick={() => {
              onTrack({
                title: title.trim(),
                entity_ids: entityIds.split(",").map((id) => id.trim()).filter(Boolean),
                interval_minutes: Number(interval) || 60,
              })
              setOpen(false)
            }}
          >
            Track
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
