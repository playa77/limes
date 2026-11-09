// src/views/query-cypher-view.tsx
// FR-DC-032: direct read-only queries via POST /query/cypher; write-clause
// rejection surfaces the API's parse-level error verbatim; the session
// history persists for the session and saves are one click away.

import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { useSession } from "@/state/session"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { PageHeader, Region, RegionError, ViewPage } from "@/components/page-shell"
import { QueryResultSurface } from "@/components/query-results"
import { CodeBlock } from "@/components/reui/code-block/code-block"

function report(error: Error): { title: string; description: string } {
  if (error instanceof ApiError) {
    return { title: `API error ${error.status}`, description: error.detail }
  }
  if (error instanceof ApiUnreachable) {
    return { title: "API transport unavailable", description: error.message }
  }
  return { title: "Query failed", description: error.message }
}

export function QueryCypherView() {
  const [cypher, setCypher] = useState("")
  const [jsonParams, setJsonParams] = useState("{}")
  const run = useMutation({
    mutationFn: (input: { cypher: string; params: Record<string, unknown> }) =>
      apiClient.queryCypher(input.cypher, input.params),
    onSuccess: (outcome) => {
      useSession.getState().publish(outcome)
    },
    onError: (error) => toast.error(report(error).title, { description: report(error).description }),
  })

  const params = safeParams(jsonParams)

  return (
    <ViewPage>
      <PageHeader
        title="Cypher console"
        description="Read-only queries; rejected writes surface the API error verbatim"
      />
      <Region spacing="sm">
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (cypher.trim() === "") return
            if (params === null) {
              toast.error("Params are not valid JSON.", {
                description: "Fix the parameters object before running.",
              })
              return
            }
            run.mutate({ cypher: cypher, params })
          }}
        >
          <Label htmlFor="cypher-text">Cypher</Label>
          <Textarea
            id="cypher-text"
            value={cypher}
            onChange={(event) => setCypher(event.target.value)}
            className="min-h-24 font-mono text-xs"
            spellCheck={false}
          />
          <div className="flex flex-col gap-1">
            <Label htmlFor="cypher-params" className="text-xs">
              Parameters (JSON object, travels as parameters — never in the query text)
            </Label>
            <Input
              id="cypher-params"
              value={jsonParams}
              onChange={(event) => setJsonParams(event.target.value)}
              className={`h-8 font-mono text-xs ${params === null ? "aria-invalid:border-destructive" : ""}`}
              aria-invalid={params === null}
            />
          </div>
          <div className="flex items-center gap-2">
            <Button type="submit" size="sm" disabled={run.isPending}>
              {run.isPending ? "Running…" : "Run"}
            </Button>
            <SaveCurrentCypher cypher={cypher} />
          </div>
        </form>
      </Region>

      {run.isError ? (
        <Region
          spacing="sm"
          title="Rejected"
          description="The API's parse-level wording is diagnostic signal (FR-DC-032)."
        >
          <RegionError
            detail={
              run.error instanceof ApiError
                ? `API error ${run.error.status}: ${run.error.detail}`
                : run.error.message
            }
            onRetry={() => run.reset()}
          />
        </Region>
      ) : null}

      <OutcomesRegion />

      <Region spacing="sm" title="Session history" description="Queries executed in this session (FR-DC-032).">
        <SessionCypherHistory />
      </Region>
    </ViewPage>
  )
}

function safeParams(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text)
    if (parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)) {
      return parsed as Record<string, unknown>
    }
    return null
  } catch {
    return null
  }
}

function SaveCurrentCypher({ cypher }: { cypher: string }) {
  const save = useMutation({
    mutationFn: (name: string) =>
      apiClient.saveQuery(name, cypher, { surface: "cypher" }),
    onSuccess: () => toast.success("Saved query stored."),
    onError: (error) => toast.error(report(error).title, { description: report(error).description }),
  })
  const [name, setName] = useState("Saved Cypher query")
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">Save query</Button>
      </DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Save this query</DialogTitle>
        </DialogHeader>
        <Label htmlFor="saved-cypher-name">Name</Label>
        <Input id="saved-cypher-name" value={name} onChange={(e) => setName(e.target.value)} />
        <pre className="max-h-32 overflow-auto text-xs">
          <CodeBlock code={cypher} language="cypher" variant="ghost" />
        </pre>
        <DialogFooter>
          <Button
            size="sm"
            type="button"
            disabled={save.isPending || name.trim() === "" || cypher.trim() === ""}
            onClick={() => save.mutate(name.trim())}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function SessionCypherHistory() {
  const cypherRuns = useSession((s) => s.history).filter((b) => b.outcome.source !== "nl")
  if (cypherRuns.length === 0) {
    return <p className="text-muted-foreground text-xs">No queries executed in this session yet.</p>
  }
  return (
    <ul className="flex flex-col gap-1">
      {[...cypherRuns].reverse().map((bundle) => (
        <li key={bundle.id} className="rounded-md border px-2 py-1.5">
          <CodeBlock code={bundle.cypher ?? ""} language="cypher" variant="ghost" maxLines={4} />
          <p className="text-muted-foreground mt-1 text-xs">
            {new Date(bundle.publishedAt).toLocaleTimeString()} — {bundle.outcome.source}
          </p>
        </li>
      ))}
    </ul>
  )
}

/** The outcome surface reads the last published bundle from the store (never
 *  the run object): the history is the true source for result panes. */
function OutcomesRegion() {
  const lastOutcome = useSession((s) => s.lastOutcome)
  if (lastOutcome === null) return null
  return (
    <Region
      spacing="sm"
      title="Outcome"
      description="Coverage, diagnosis and the three visualizations share one selection state."
    >
      <QueryResultSurface bundle={lastOutcome} />
    </Region>
  )
}
