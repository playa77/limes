// src/views/developments-view.tsx
// DC-16: cross-source temporal investigation. Evidence, event candidates and
// recorded reviews all travel through HTTP; decisions, assessment and
// independence stay separate; dependent reports and alternatives are
// preserved and never silently merged.

import { useState } from "react"
import { Link } from "react-router"
import { useMutation, useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { toast } from "sonner"
import type { DevelopmentEvidence, EventMatch } from "@/api/types"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

/** DC-16 (D-86r era) rule carried into the web client verbatim from the
 * retired Qt panel: a cross-source chronology is never a causal claim. */
export const NO_CAUSALITY_NOTE = "\nChronology implies neither causation nor misconduct."

export function DevelopmentsView() {
  const [investigationId, setInvestigationId] = useState("")
  const list = useQuery({
    queryKey: ["api", "news", "investigations"],
    queryFn: () => apiClient.newsInvestigations(),
    staleTime: 30_000,
  })

  const [typedId, setTypedId] = useState("")
  const activeId = investigationId.trim()

  const developments = useQuery({
    queryKey: ["api", "news", "developments", activeId],
    queryFn: () => apiClient.newsDevelopments(activeId),
    enabled: activeId !== "",
    staleTime: 20_000,
    retry: 1,
  })

  return (
    <ViewPage>
      <PageHeader
        title="Developments"
        description="Cross-source evidence with explicit alternatives, disputes and gaps"
        actions={
          <div className="flex items-center gap-2">
            <Select
              value={activeId === "" ? undefined : activeId}
              onValueChange={(value) => setInvestigationId(value)}
            >
              <SelectTrigger size="sm" className="h-7 w-60" aria-label="Pick an investigation">
                <SelectValue placeholder="Pick an investigation" />
              </SelectTrigger>
              <SelectContent>
                {(list.data ?? []).map((item) => (
                  <SelectItem key={item.investigation_id} value={item.investigation_id}>
                    {item.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <input
              aria-label="Load investigation by id"
              value={typedId}
              onChange={(event) => setTypedId(event.target.value)}
              placeholder="or type an id"
              className="border-input bg-background focus-visible:ring-ring/50 h-7 w-40 rounded-md border px-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2"
              onKeyDown={(event) => {
                if (event.key === "Enter") setInvestigationId(typedId)
              }}
            />
          </div>
        }
      />

      {activeId === "" ? (
        <Region>
          <EmptyNote>Pick an investigation to load its evidence, candidates and reviews.</EmptyNote>
        </Region>
      ) : developments.isPending ? (
        <Region title="Evidence">
          <RegionSkeleton rows={5} />
        </Region>
      ) : developments.isError ? (
        <Region>
          <RegionError detail={developments.error.message} onRetry={() => void developments.refetch()} />
        </Region>
      ) : developments.data ? (
        <>
          {developments.data.diagnosis.length > 0 ? (
            <Region spacing="sm" title="Diagnosis">
              <ul className="list-inside list-disc text-xs">
                {developments.data.diagnosis.map((line) => (
                  <li key={line} className="text-muted-foreground">
                    {line}
                  </li>
                ))}
              </ul>
            </Region>
          ) : null}
          <EvidenceList evidence={developments.data.evidence} truncated={developments.data.truncated} />
          <EventMatches
            candidates={developments.data.candidates}
            investigationId={activeId}
            reviews={developments.data.reviews}
          />
          <p className="text-muted-foreground text-xs">{NO_CAUSALITY_NOTE}</p>
          {developments.data.locations.length > 0 ? (
            <Region spacing="sm" title="Locations" description="Finite coordinates supplied by the API; nothing is inferred">
              <ul className="flex flex-wrap gap-2 text-xs">
                {developments.data.locations.map((location, index) => (
                  <li
                    key={index}
                    className="border-border rounded-md border px-2 py-1 font-mono"
                  >
                    {JSON.stringify(location)}
                  </li>
                ))}
              </ul>
            </Region>
          ) : null}
        </>
      ) : null}
    </ViewPage>
  )
}

function EvidenceList({
  evidence,
  truncated,
}: {
  evidence: DevelopmentEvidence[]
  truncated: boolean
}) {
  return (
    <Region
      spacing="sm"
      title="Evidence"
      description={`${evidence.length} coded rows; dependent reports stay marked`}
    >
      {evidence.length === 0 ? (
        <EmptyNote>No evidence rows for this window.</EmptyNote>
      ) : (
        <ul className="flex flex-col">
          {evidence.map((row) => (
            <li
              key={row.evidence_id}
              className="border-border/60 flex flex-col gap-1 border-b py-2 last:border-b-0"
            >
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline">{row.kind}</Badge>
                <span className="font-medium">
                  {row.subject_label} ({row.relation}) {row.object_label}
                </span>
                {row.dependency_key ? (
                  <Badge variant="warning-light">dependent: {row.dependency_key}</Badge>
                ) : (
                  <Badge variant="info-light">direct</Badge>
                )}
                <Link
                  to={`/entity/${encodeURIComponent(row.subject_id)}`}
                  className="text-primary text-xs underline"
                >
                  subject
                </Link>
                <Link
                  to={`/entity/${encodeURIComponent(row.object_id)}`}
                  className="text-primary text-xs underline"
                >
                  object
                </Link>
              </div>
              {Object.keys(row.properties).length > 0 ? (
                <pre className="text-muted-foreground max-h-32 overflow-auto text-[11px]">
                  {JSON.stringify(row.properties, null, 2)}
                </pre>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {truncated ? (
        <EmptyNote>The API truncated this window; narrow the investigation to see more.</EmptyNote>
      ) : null}
    </Region>
  )
}

const DECISIONS = ["unresolved", "same_event", "different_event"] as const
const INDEPENDENCE = ["unknown", "dependent", "independent"] as const

function EventMatches({
  candidates,
  investigationId,
  reviews,
}: {
  candidates: EventMatch[]
  investigationId: string
  reviews: { request_id: string; left: string; right: string; decision: string; rationale: string; recorded_at: string }[]
}) {
  const [selected, setSelected] = useState<EventMatch | null>(null)

  return (
    <Region
      spacing="sm"
      title="Event candidates"
      description="Event matching is unresolved until it is reviewed here; reviews are operator-only evidence"
    >
      {candidates.length === 0 ? (
        <EmptyNote>No unresolved event candidates in this window.</EmptyNote>
      ) : null}
      <ul className="flex flex-col">
        {candidates.map((candidate) => (
          <li
            key={candidate.candidate_id}
            className="border-border/60 flex flex-wrap items-center gap-2 border-b py-2 text-xs last:border-b-0"
          >
            <Badge variant={candidate.decision === "unresolved" ? "warning-light" : "info-light"}>
              {candidate.decision}
            </Badge>
            <span>
              <EntityLink id={candidate.left} /> ↔ <EntityLink id={candidate.right} />
            </span>
            <Badge variant="outline">{candidate.assessment}</Badge>
            <Badge variant="outline">{candidate.independence}</Badge>
            <Button
              size="xs"
              variant="ghost"
              className="ms-auto"
              onClick={() => setSelected(candidate)}
            >
              Review
            </Button>
          </li>
        ))}
      </ul>
      {selected ? (
        <ReviewForm
          investigationId={investigationId}
          candidate={selected}
          onDone={() => setSelected(null)}
        />
      ) : null}
      {reviews.length > 0 ? (
        <div className="mt-3">
          <p className="mb-1 text-xs font-semibold">Recorded reviews</p>
          <ul className="flex flex-col gap-1">
            {reviews.map((review) => (
              <li key={review.request_id} className="border-border/60 border-b py-1 text-xs">
                <Badge variant="outline">{review.decision}</Badge>{" "}
                <EntityLink id={review.left} /> ↔ <EntityLink id={review.right} />{" "}
                <span className="text-muted-foreground">
                  {review.recorded_at} — {review.rationale}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </Region>
  )
}

function EntityLink({ id }: { id: string }) {
  return (
    <Link to={`/entity/${encodeURIComponent(id)}`} className="font-mono text-xs underline">
      {id}
    </Link>
  )
}

function ReviewForm({
  investigationId,
  candidate,
  onDone,
}: {
  investigationId: string
  candidate: EventMatch
  onDone: () => void
}) {
  const [decision, setDecision] = useState<string>("unresolved")
  const [independence, setIndependence] = useState<string>("unknown")
  const [rationale, setRationale] = useState("")

  const review = useMutation({
    mutationFn: () =>
      apiClient.reviewEventMatch(investigationId, {
        request_id: `${candidate.candidate_id}-${Date.now()}`,
        left: candidate.left,
        right: candidate.right,
        decision,
        rationale,
      }),
    onSuccess: () => {
      toast.success("Review recorded; reload to see it in the retained history.")
      onDone()
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : "Review failed"),
  })

  const rationaleValid = rationale.trim().length > 0

  return (
    <form
      className="border-border mt-2 flex flex-col gap-2 rounded-lg border p-3"
      onSubmit={(event) => {
        event.preventDefault()
        if (rationaleValid) review.mutate()
      }}
    >
      <p className="text-xs font-semibold">
        Review {candidate.candidate_id}: {candidate.left} ↔ {candidate.right}
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Decision</Label>
          <Select value={decision} onValueChange={setDecision}>
            <SelectTrigger size="sm" className="h-7 w-44" aria-label="Decision">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {DECISIONS.map((entry) => (
                <SelectItem key={entry} value={entry}>
                  {entry}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs">Independence</Label>
          <Select value={independence} onValueChange={setIndependence}>
            <SelectTrigger size="sm" className="h-7 w-44" aria-label="Independence">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {INDEPENDENCE.map((entry) => (
                <SelectItem key={entry} value={entry}>
                  {entry}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <Textarea
        value={rationale}
        onChange={(event) => setRationale(event.target.value)}
        rows={2}
        placeholder="Why these two dispatches are (or are not) the same event"
        className="min-h-14"
        aria-label="Review rationale"
      />
      <div className="flex items-center gap-2">
        <Button size="sm" type="submit" disabled={review.isPending || !rationaleValid}>
          Record event-match review
        </Button>
        <span className="text-muted-foreground text-xs">
          No causal or misconduct inference is attached by the client (DC-16).
        </span>
      </div>
    </form>
  )
}
