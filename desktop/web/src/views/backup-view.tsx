// src/views/backup-view.tsx
// FR-DC-060..063: operator-only backup over HTTP. The consequence text is
// named verbatim before any submission; the request id is idempotent; status,
// bounded output and the dump name are polled; a successful run verifies the
// API health; prerequisites gate the action with precise reasons; a failed
// observation never triggers an automatic retry, and disconnecting does not
// cancel the server job.

import { useEffect, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { useCapabilityQuery } from "@/hooks/use-connection"
import { useSession } from "@/state/session"
import type { OperationJob } from "@/api/types"
import { Badge } from "@/components/reui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/reui/alert"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Button } from "@/components/ui/button"
import { PageHeader, Region, RegionSkeleton, EmptyNote, ViewPage } from "@/components/page-shell"

const CONSEQUENCE_TEXT =
  "Neo4j unavailable during backup; clean shutdown can take up to 180 seconds"

function report(error: Error): { title: string; description: string } {
  if (error instanceof ApiError) {
    return { title: `API error ${error.status}`, description: error.detail }
  }
  if (error instanceof ApiUnreachable) {
    return { title: "API transport unavailable", description: error.message }
  }
  return { title: "Backup failed", description: error.message }
}

export function BackupView() {
  const queryClient = useQueryClient()
  const reachability = useSession((s) => s.reachability)
  const capabilities = useCapabilityQuery()
  const caps = capabilities.data ?? null
  const [job, setJob] = useState<OperationJob | null>(null)
  const [output, setOutput] = useState("")
  const [dump, setDump] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<string | null>(null)
  const requestId = useSession((s) => s.backupRequestId)
  const setRequestId = useSession((s) => s.setBackupRequestId)
  const [submitting, setSubmitting] = useState(requestId !== null)
  const [observing, setObserving] = useState(requestId !== null)

  // Capabilities decide the inline prerequisite reason (FR-DC-063).
  const reasons: string[] = []
  if (reachability === "unknown") reasons.push("Checking API reachability before backup.")
  if (reachability === "unreachable") {
    reasons.push("Backup unavailable: API unreachable.")
  }
  if (reachability === "reachable" && caps === null) {
    reasons.push("Backup requires an operator credential.")
  }
  if (reachability === "reachable" && caps !== null && caps.backup !== true) {
    reasons.push("API does not offer backup capability.")
  }
  useEffect(() => {
    if (!observing || requestId === null) return
    let cancelled = false
    let timer: number | undefined

    async function poll() {
      try {
        const next = await apiClient.operationStatus(requestId!)
        if (cancelled) return
        setJob(next)
        setOutput(next.output)
        const filename = /limes-[0-9T]+-[a-f0-9]+\.dump/.exec(next.output)?.[0] ?? null
        setDump(filename)
        if (next.status === "failed" || next.status === "cancelled") {
          setOutcome(next.status === "cancelled"
            ? "Backup cancelled. No automatic retry."
            : "Backup failed. No automatic retry.")
          setSubmitting(false)
          setObserving(false)
          return
        }
        if (next.status === "succeeded") {
          let healthy = false
          try {
            const health = await apiClient.health()
            healthy = health.status === "ok" && health.neo4j
          } catch { /* The completed job stays completed if health cannot be confirmed. */ }
          if (cancelled) return
          setOutcome(healthy
            ? `Backup complete; API healthy. Dump: ${filename ?? "not reported"}`
            : "Backup completed; API health is not confirmed. Check connection before continuing.")
          setSubmitting(false)
          setObserving(false)
          void queryClient.invalidateQueries({ queryKey: ["api", "health"] })
          return
        }
        timer = window.setTimeout(poll, 1_000)
      } catch {
        if (cancelled) return
        setOutcome("Observation interrupted; the server job continues. Use its ID to check status.")
        setSubmitting(false)
        setObserving(false)
      }
    }

    void poll()
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [observing, requestId, queryClient])

  async function submit() {
    const id = crypto.randomUUID()
    setObserving(false)
    setJob(null)
    setRequestId(id)
    setSubmitting(true)
    setOutcome(null)
    setOutput("")
    setDump(null)
    try {
      const firstJob = await apiClient.submitBackup(id)
      setJob(firstJob)
      setObserving(true)
      setOutput((current) => `${current}Backup job: ${firstJob.job_id}\n`)
    } catch (error) {
      setOutcome("Backup request failed; check the operator credential and job status.")
      setSubmitting(false)
      if (error instanceof Error) {
        setOutput((current) => `${current}${report(error).title}: ${report(error).description}\n`)
      }
    }
  }

  return (
    <ViewPage>
      <PageHeader
        title="Backup"
        description="Operator job over HTTP; the supervisor owns the physical dump cycle"
      />

      <Region spacing="sm" title="Run a backup">
        <Alert variant="warning" className="mb-3">
          <AlertTitle>Consequence</AlertTitle>
          <AlertDescription>{CONSEQUENCE_TEXT}</AlertDescription>
        </Alert>
        {reasons.length > 0 ? (
          <div role="status" className="text-xs">
            {reasons.map((reason) => (
              <p key={reason} className="text-muted-foreground py-0.5">
                {reason}
              </p>
            ))}
          </div>
        ) : submitting ? (
          <p className="text-muted-foreground text-xs">
            Backup in progress. Leaving this view does not cancel the server job.
          </p>
        ) : null}
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" disabled={reasons.length > 0 || submitting || reachability !== "reachable" || caps?.backup !== true}>
              Run backup
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Confirm the consequence</AlertDialogTitle>
              <AlertDialogDescription>
                This requests a server backup using your operator credential. {CONSEQUENCE_TEXT}.
                The request is idempotent; a failed job is never retried automatically.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={() => submit()}>Run backup</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        {outcome !== null ? (
          <p className="mt-2 text-xs" role="status">
            {outcome}
          </p>
        ) : null}
        {requestId !== null ? (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline">request {requestId}</Badge>
            {job !== null ? <Badge variant="info-light">status: {job.status}</Badge> : null}
            {dump !== null ? <Badge variant="success-light">dump {dump}</Badge> : null}
          </div>
        ) : null}
      </Region>

      <Region spacing="sm" title="Bounded output" description="The server's streamed output up to a bounded size">
        {submitting && job === null ? <RegionSkeleton rows={2} /> : null}
        <pre
          className="max-h-64 min-h-16 overflow-auto rounded-md border p-2 text-xs"
          data-testid="backup-output"
        >
          {output || "No output yet."}
        </pre>
      </Region>

      {reachability === "unreachable" ? (
        <Region spacing="sm" title="Degraded state">
          <EmptyNote>
            No backup activity is possible while the API is unreachable; the panel keeps retrying
            health checks in the header, not jobs.
          </EmptyNote>
        </Region>
      ) : null}

      <Region spacing="sm" title="Job status polling">
        {requestId !== null ? (
          job !== null ? <JobStatus data={job} /> : <EmptyNote>No status response yet; the request ID is retained above.</EmptyNote>
        ) : (
          <EmptyNote>No job submitted in this session yet.</EmptyNote>
        )}
      </Region>
    </ViewPage>
  )
}

function JobStatus({ data }: { data: OperationJob }) {
  return (
    <dl className="grid grid-cols-[minmax(8rem,10rem),minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
      <dt className="text-muted-foreground">job id</dt>
      <dd className="font-mono break-words">{data.job_id}</dd>
      <dt className="text-muted-foreground">status</dt>
      <dd>
        <Badge variant={data.status === "succeeded" ? "success-light" : data.status === "failed" ? "destructive-light" : "info-light"}>
          {data.status}
        </Badge>
      </dd>
      <dt className="text-muted-foreground">command</dt>
      <dd>{data.request.command}</dd>
      <dt className="text-muted-foreground">created</dt>
      <dd className="tabular-nums">{data.created_at}</dd>
      <dt className="text-muted-foreground">updated</dt>
      <dd className="tabular-nums">{data.updated_at}</dd>
      <dt className="text-muted-foreground">exit code</dt>
      <dd className="tabular-nums">{data.exit_code ?? "—"}</dd>
    </dl>
  )
}
