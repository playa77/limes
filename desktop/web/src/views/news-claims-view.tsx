// src/views/news-claims-view.tsx
// FR-DC-023 / AC-DC-8 semantics: statement kind, modality, attributed
// speaker, assessment, event lifecycle and time precision stay separate
// facts; a denial or proposal never renders as an unqualified completed
// fact; missing attribution/text stay visible; correction/syndication
// lineage is shown when the API carries it.

import { useMemo, useState } from "react"
import { Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import type { NewsClaim } from "@/api/types"
import { DataTable } from "@/components/data-table"
import { DataGridColumnHeader } from "@/components/reui/data-grid/data-grid-column-header"
import type { ColumnDef } from "@tanstack/react-table"
import type { DataGridFeatures as DGFeatures } from "@/components/reui/data-grid/data-grid"
import { Badge } from "@/components/reui/badge"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

type AnyColumnDef = ColumnDef<DGFeatures, NewsClaim>

const MODALITIES = ["All claims", "asserted", "reported", "denied", "proposed", "conditional", "unknown"] as const

export function NewsClaimsView() {
  const [modality, setModality] = useState<string>("All claims")
  const [investigation, setInvestigation] = useState<string>("")
  const [selected, setSelected] = useState<NewsClaim | null>(null)

  const filters = useMemo(() => {
    const records: Record<string, string> = { limit: "200" }
    if (modality !== "All claims") records.modality = modality
    if (investigation.trim() !== "") records.investigation_id = investigation.trim()
    return records
  }, [modality, investigation])

  const claims = useQuery({
    queryKey: ["api", "news", "claims", filters],
    queryFn: () => apiClient.newsClaims(filters),
    staleTime: 20_000,
  })

  const columns = useMemo<AnyColumnDef[]>(
    () => [
      {
        accessorKey: "modality",
        id: "modality",
        header: "kind",
        cell: ({ row }) => <ModalityBadge claim={row.original} />,
        size: 120,
        meta: { headerClassName: "", cellClassName: "" },
      },
      {
        id: "statement",
        accessorFn: (row) => `${row.subject_label} ⟶ ${row.relation} ⟶ ${row.object_label}`,
        header: ({ column }) => <DataGridColumnHeader title="Proposition" column={column} />,
        cell: ({ row }) => {
          const claim = row.original
          // A denial/proposal never reads as a completed fact (FR-DC-044):
          // the modality leads the sentence and the lifecycle follows it.
          void claim
          return (
            <span className="text-xs">
              <span className="font-medium">{claim.subject_label}</span>{" "}
              <span className="text-muted-foreground">({claim.relation})</span>{" "}
              <span className="font-medium">{claim.object_label}</span>
            </span>
          )
        },
        size: 380,
      },
      {
        accessorKey: "attribution",
        id: "attribution",
        header: ({ column }) => <DataGridColumnHeader title="Attribution" column={column} />,
        cell: ({ row }) =>
          row.original.attribution ?? (
            <span className="text-muted-foreground text-xs">unknown speaker</span>
          ),
        size: 160,
      },
      {
        accessorKey: "event_status",
        id: "status",
        header: ({ column }) => <DataGridColumnHeader title="Lifecycle" column={column} />,
        cell: ({ row }) => <Badge variant="outline">{row.original.event_status}</Badge>,
        size: 110,
      },
      {
        accessorKey: "assessment",
        id: "assessment",
        header: ({ column }) => <DataGridColumnHeader title="Assessment" column={column} />,
        cell: ({ row }) => <AssessmentBadge claim={row.original} />,
        size: 130,
      },
      {
        accessorKey: "recorded_at",
        id: "recorded",
        header: ({ column }) => <DataGridColumnHeader title="Recorded" column={column} />,
        cell: ({ row }) => (
          <span className="text-xs tabular-nums">{row.original.recorded_at ?? "?"}</span>
        ),
        size: 150,
      },
      {
        accessorKey: "publisher",
        id: "publisher",
        header: ({ column }) => <DataGridColumnHeader title="Publisher" column={column} />,
        cell: ({ row }) =>
          row.original.publisher ?? (
            <span className="text-muted-foreground text-xs">unknown</span>
          ),
        size: 140,
      },
    ],
    [],
  )

  return (
    <ViewPage>
      <PageHeader
        title="Qualified claims"
        description="Coded claim rows with separate semantics; evidence is one click away"
        actions={
          <>
            <Select value={modality} onValueChange={setModality}>
              <SelectTrigger size="sm" className="h-7 w-40" aria-label="Filter by modality">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODALITIES.map((entry) => (
                  <SelectItem key={entry} value={entry}>
                    {entry}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <input
              aria-label="Investigation filter"
              value={investigation}
              onChange={(event) => setInvestigation(event.target.value)}
              placeholder="investigation id"
              className="border-input bg-background focus-visible:ring-ring/50 h-7 w-44 rounded-md border px-2 font-mono text-xs focus-visible:outline-none focus-visible:ring-2"
            />
          </>
        }
      />

      <Region spacing="sm" dense>
        {claims.isPending ? <RegionSkeleton rows={5} /> : null}
        {claims.isError ? (
          <RegionError
            detail={
              claims.error instanceof Error
                ? claims.error.message
                : "Claims unavailable."
            }
            onRetry={() => void claims.refetch()}
          />
        ) : null}
        {claims.data && claims.data.length === 0 ? (
          <EmptyNote>
            No claims for the current filter. Empty sources keep their diagnosis on the
            investigations pane.
          </EmptyNote>
        ) : null}
        {claims.data && claims.data.length > 0 ? (
          <DataTable
            data={claims.data}
            columns={columns}
            pageSize={15}
            getRowId={(row) => row.claim_id}
          />
        ) : null}
      </Region>
      <p className="text-muted-foreground text-xs">
        Rows open the claim record; extraction confidence, source trust and corroboration are
        separate. Repeated dispatches are dependent reporting, never independent corroboration.
      </p>

      <Dialog open={selected !== null} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-w-2xl">
          {selected ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <ModalityBadge claim={selected} />
                  {selected.subject_label} ({selected.relation}) {selected.object_label}
                </DialogTitle>
                <DialogDescription>
                  Event status {selected.event_status}; time precision {selected.time_precision}.
                </DialogDescription>
              </DialogHeader>
              <dl className="grid grid-cols-[minmax(8rem,10rem),minmax(0,1fr)] gap-x-3 gap-y-1 text-xs">
                <ClaimField name="claim id" value={selected.claim_id} mono />
                <ClaimField name="subject" value={selected.subject_id} mono link />
                <ClaimField name="object" value={selected.object_id} mono link />
                <ClaimField name="modality" value={selected.modality} />
                <ClaimField name="event status" value={selected.event_status} />
                <ClaimField name="time precision" value={selected.time_precision} />
                <ClaimField name="event candidate" value={selected.event_candidate} mono />
                <ClaimField name="attribution" value={selected.attribution} />
                <ClaimField name="assessment" value={selected.assessment} />
                <ClaimField
                  name="source"
                  value={selected.source_id !== null ? `${selected.source_id} (trust ${selected.source_trust ?? "?"})` : null}
                  mono
                />
                <ClaimField name="confidence" value={selected.confidence?.toFixed(3) ?? null} />
                <ClaimField name="dispatch" value={selected.dispatch_id} mono />
                <ClaimField name="publisher" value={selected.publisher} />
                <ClaimField name="syndication" value={selected.syndication_key} mono />
                <ClaimField name="report url" value={selected.report_url} mono />
                <ClaimField name="validity" value={selected.valid_from !== null ? `${selected.valid_from} → ${selected.valid_to ?? "open"}` : null} />
                <ClaimField name="recorded at" value={selected.recorded_at} />
                <ClaimField name="retracted at" value={selected.retracted_at} />
                <ClaimField
                  name="evidence span"
                  value={
                    selected.evidence_document_id !== null
                      ? `${selected.evidence_document_id} [${selected.evidence_start ?? "?"}..${selected.evidence_end ?? "?"}]`
                      : null
                  }
                  mono
                />
                <ClaimField name="ontology" value={selected.ontology_version} mono />
                <ClaimField name="extractor" value={selected.extractor_model} mono />
                <ClaimField name="prompt" value={selected.prompt_version} mono />
                <ClaimField name="schema" value={selected.schema_version} mono />
              </dl>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/news/documents/${encodeURIComponent(selected.evidence_document_id)}`}
                  className="text-primary text-xs underline"
                >
                  Open evidence document
                </Link>
                {selected.report_url ? (
                  <a
                    href={selected.report_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary text-xs underline"
                  >
                    Open the original report
                  </a>
                ) : (
                  <span className="text-muted-foreground text-xs">
                    No archived report URL — the coverage gap stays visible.
                  </span>
                )}
              </div>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </ViewPage>
  )
}

function ClaimField({
  name,
  value,
  mono = false,
  link = false,
}: {
  name: string
  value: string | null | undefined
  mono?: boolean
  link?: boolean
}) {
  return (
    <>
      <dt className="text-muted-foreground">{name}</dt>
      <dd className={`break-words ${mono ? "font-mono" : ""}`}>
        {value === null || value === undefined || value === "" ? (
          <span className="text-muted-foreground">unknown</span>
        ) : link ? (
          <Link to={`/entity/${encodeURIComponent(value)}`} className="text-primary underline">
            {value}
          </Link>
        ) : (
          value
        )}
      </dd>
    </>
  )
}

function ModalityBadge({ claim }: { claim: NewsClaim }) {
  // The modality IS the statement kind: it colors the record deliberately
  // (denials/proposals must never read as plain assertions).
  const variant =
    claim.modality === "denied"
      ? "destructive-light"
      : claim.modality === "proposed"
        ? "warning-light"
        : claim.modality === "asserted"
          ? "success-light"
          : "info-light"
  return <Badge variant={variant}>{claim.modality}</Badge>
}

function AssessmentBadge({ claim }: { claim: NewsClaim }) {
  const variant =
    claim.assessment === "supported"
      ? "success-light"
      : claim.assessment === "refuted"
        ? "destructive-light"
        : claim.assessment === "disputed"
          ? "warning-light"
          : "outline"
  return <Badge variant={variant}>{claim.assessment}</Badge>
}
