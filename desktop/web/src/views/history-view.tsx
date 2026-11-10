// src/views/history-view.tsx
// FR-DC-033 + session history: every published outcome (NL, builder, cypher)
// is recorded here with repetition preserved (each execution is history), and
// saved queries list/create/delete through the three saved-query endpoints.

import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError } from "@/api/errors"
import { toast } from "sonner"
import { useSession, type Bundle } from "@/state/session"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { PageHeader, Region, RegionError, RegionSkeleton, EmptyNote, ViewPage } from "@/components/page-shell"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { CodeBlock } from "@/components/reui/code-block/code-block"

export function HistoryView() {
  const [tab, setTab] = useState("history")
  return (
    <ViewPage>
      <PageHeader
        title="History & saved queries"
        description="Every execution is recorded; saved queries pin the reusable ones"
      />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="history">Session history</TabsTrigger>
          <TabsTrigger value="saved">Saved queries</TabsTrigger>
        </TabsList>
        <TabsContent value="history">
          <HistoryList />
        </TabsContent>
        <TabsContent value="saved">
          <SavedQueriesPanel />
        </TabsContent>
      </Tabs>
    </ViewPage>
  )
}

function HistoryList() {
  const history = useSession((s) => s.history)
  if (history.length === 0) {
    return (
      <Region>
        <EmptyNote>No outcomes published yet in this session.</EmptyNote>
      </Region>
    )
  }
  return (
    <ul className="flex flex-col gap-3">
      {[...history].reverse().map((bundle) => (
        <HistoryEntry key={bundle.id} bundle={bundle} />
      ))}
    </ul>
  )
}

function HistoryEntry({ bundle }: { bundle: Bundle }) {
  const [open, setOpen] = useState(false)
  const graph = bundle.outcome.results
  return (
    <li>
      <Region spacing="sm">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{bundle.source}</Badge>
          <span className="text-muted-foreground text-xs tabular-nums">
            {new Date(bundle.publishedAt).toLocaleTimeString()}
          </span>
          {graph !== null ? (
            <span className="text-muted-foreground text-xs tabular-nums">
              {graph.nodes.length} nodes, {graph.edges.length} assertion edges
            </span>
          ) : (
            <span className="text-muted-foreground text-xs">no executed read</span>
          )}
          {bundle.diagnosis !== null ? (
            <Badge variant="warning-light">empty: diagnosis attached</Badge>
          ) : null}
          <Button
            size="xs"
            variant="ghost"
            className="ms-auto"
            onClick={() => setOpen((current) => !current)}
            aria-expanded={open}
          >
            {open ? "Hide" : "Show"}
          </Button>
        </div>
        {open ? (
          <div className="mt-2 flex flex-col gap-1">
            {bundle.cypher ? (
              <CodeBlock code={bundle.cypher} language="cypher" variant="ghost" maxLines={10} />
            ) : null}
            {bundle.nlq !== null && bundle.nlq.validation_errors.length > 0 ? (
              <p className="text-destructive text-xs">
                {bundle.nlq.validation_errors.join(" | ")}
              </p>
            ) : null}
            {bundle.nlq !== null && bundle.nlq.notes.length > 0 ? (
              <p className="text-muted-foreground text-xs">{bundle.nlq.notes.join(" | ")}</p>
            ) : null}
          </div>
        ) : null}
      </Region>
    </li>
  )
}

function SavedQueriesPanel() {
  const queryClient = useQueryClient()
  const list = useQuery({
    queryKey: ["api", "saved-queries"],
    queryFn: () => apiClient.savedQueries(),
    staleTime: 5_000,
  })
  const remove = useMutation({
    mutationFn: (id: string) => apiClient.deleteSavedQuery(id),
    onSuccess: () => {
      toast.success("Saved query deleted.")
      void queryClient.invalidateQueries({ queryKey: ["api", "saved-queries"] })
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError ? `API error ${error.status}` : "Delete failed",
        { description: error instanceof ApiError ? error.detail : error.message },
      ),
  })

  return (
    <Region spacing="sm" title="Saved queries">
      {list.isPending ? <RegionSkeleton rows={3} /> : null}
      {list.isError ? (
        <RegionError
          detail={
            list.error instanceof ApiError
              ? `API error ${list.error.status}: ${list.error.detail}`
              : "Saved queries unavailable."
          }
          onRetry={() => void list.refetch()}
        />
      ) : null}
      {list.data && list.data.length === 0 ? (
        <EmptyNote>No saved queries yet — save one from any query surface.</EmptyNote>
      ) : null}
      <ul className="flex flex-col gap-2">
        {(list.data ?? []).map((saved) => (
          <li key={saved.saved_query_id} className="rounded-lg border p-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{saved.question}</span>
              {saved.pinned ? <Badge variant="primary-light">pinned</Badge> : null}
              <Badge variant="outline">{saved.ontology_version}</Badge>
              <span className="text-muted-foreground text-xs tabular-nums">
                {saved.result_count} rows ·{" "}
                {saved.created_at ? new Date(saved.created_at).toLocaleString() : "unknown time"}
              </span>
              <Button
                size="xs"
                variant="ghost"
                className="ms-auto"
                onClick={() => remove.mutate(saved.saved_query_id)}
                aria-label={`Delete saved query ${saved.question}`}
              >
                Delete
              </Button>
            </div>
            <CodeBlock code={saved.cypher} language="cypher" variant="ghost" maxLines={5} />
          </li>
        ))}
      </ul>
      <p className="text-muted-foreground mt-2 text-xs">
        Executing a saved query is not wired from this panel by design: the query bodies are the
        same read-only surfaces as the console.
      </p>
    </Region>
  )
}
