// src/views/query-nl-view.tsx
// FR-DC-030: question in German or English; the generated Cypher is always
// displayed and always editable before execution (re-run goes through the
// Cypher endpoint read-only).

import { useState } from "react"
import { useMutation } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { useSession } from "@/state/session"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { PageHeader, Region, RegionError, ViewPage } from "@/components/page-shell"
import { QueryResultSurface } from "@/components/query-results"
import { toast } from "sonner"

function reportError(error: Error) {
  if (error instanceof ApiError) {
    // Verbatim API error body (FR-DC-032): no rephrasing, no prefix.
    toast.error(`API error ${error.status}`, { description: error.detail })
  } else if (error instanceof ApiUnreachable) {
    toast.error("API transport unavailable", { description: error.message })
  } else {
    toast.error("Query failed", { description: error.message })
  }
}

const SAMPLE_QUESTIONS = [
  "Which companies have their registered office in Berlin?",
  "Welche Personen sind Chef_executive von deutschen Unternehmen?",
  "Which entities are LOCATED_IN an administrative region with NUTS code DE11?",
]

export function QueryNlView() {
  const [question, setQuestion] = useState("")
  const [editingCypher, setEditingCypher] = useState<string | null>(null)
  const publish = useSession((s) => s.publish)
  const lastOutcome = useSession((s) => s.lastOutcome)

  const publishNl = useMutation({
    mutationFn: (q: string) => apiClient.queryNl(q),
    onSuccess: (outcome) => {
      publish(outcome)
      setEditingCypher(outcome.cypher)
      toast.success("NL query executed.")
    },
    onError: reportError,
  })

  const publishCypher = useMutation({
    mutationFn: (cypher: string) => apiClient.queryCypher(cypher, {}),
    onSuccess: (outcome) => {
      publish(outcome)
      setEditingCypher(outcome.cypher)
      toast.success("Edited Cypher executed.")
    },
    onError: reportError,
  })

  return (
    <ViewPage>
      <PageHeader
        title="Natural-language query"
        description="Ask; inspect and edit the generated Cypher before it runs"
      />
      <Region spacing="sm">
        <form
          className="flex flex-col gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (question.trim() === "") return
            publishNl.mutate(question.trim())
          }}
        >
          <Label htmlFor="nl-question">Question</Label>
          <Textarea
            id="nl-question"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={2}
            placeholder="Which German companies received permits in 2024?"
            className="min-h-16"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" size="sm" disabled={publishNl.isPending}>
              {publishNl.isPending ? "Asking…" : "Ask"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => setEditingCypher(null)}
              disabled={lastOutcome === null}
            >
              Clear outcome pane
            </Button>
          </div>
        </form>
        <div className="flex flex-wrap gap-1.5">
          {SAMPLE_QUESTIONS.map((sample) => (
            <Button
              key={sample}
              size="xs"
              variant="outline"
              onClick={() => setQuestion(sample)}
              title="Use this example question"
            >
              {sample}
            </Button>
          ))}
        </div>
      </Region>

      {publishNl.isError && question.trim() !== "" ? (
        <RegionError
          detail={
            publishNl.error instanceof ApiError
              ? `API error ${publishNl.error.status}: ${publishNl.error.detail}`
              : "The API is unreachable; no query was executed."
          }
          onRetry={() => publishNl.mutate(question.trim())}
        />
      ) : null}

      {lastOutcome !== null ? (
        <Region spacing="sm" title="Outcome" description="Coverage, diagnosis and the three visualizations share one selection state.">
          <div className="flex flex-col gap-3">
            {editingCypher !== null && lastOutcome.outcome.results !== null ? (
              <div className="flex flex-col gap-1">
                <Label htmlFor="nl-cypher-edit" className="text-xs">
                  Generated Cypher (editable; the re-run executes this read-only)
                </Label>
                <Textarea
                  id="nl-cypher-edit"
                  value={editingCypher}
                  onChange={(event) => setEditingCypher(event.target.value)}
                  className="min-h-24 font-mono text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  className="self-start"
                  disabled={publishCypher.isPending || editingCypher.trim() === ""}
                  onClick={() => publishCypher.mutate(editingCypher)}
                >
                  Re-run edited Cypher
                </Button>
              </div>
            ) : null}
            <QueryResultSurface bundle={lastOutcome} />
          </div>
        </Region>
      ) : (
        <Region>
          <p className="text-muted-foreground py-2 text-xs">
            Ask a question in German or English; the four-stage service returns
            validation/plan metadata alongside the result graph.
          </p>
        </Region>
      )}
    </ViewPage>
  )
}
