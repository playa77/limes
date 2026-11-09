// src/views/public-offices-view.tsx
// BE-56 supporting surface: per-scope roster/coverage reads with the response's
// own semantics — distinct acquired/loaded/distinct-person counts, unresolved
// identity candidates, conflicts, as-of/belief time filters and diagnosis.
// No local roster knowledge: scope codes and member fields come from the API.

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import type { ScopeCoverage } from "@/api/types"
import { DataTable } from "@/components/data-table"
import { DataGridColumnHeader } from "@/components/reui/data-grid/data-grid-column-header"
import type { DataGridFeatures } from "@/components/reui/data-grid/data-grid"
import type { ColumnDef } from "@tanstack/react-table"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"

type OfficesResponse = Awaited<ReturnType<typeof apiClient.publicOffices>>

export function PublicOfficesView() {
  const [scope, setScope] = useState("")
  const [term, setTerm] = useState("")
  const [limit, setLimit] = useState(200)
  const [applied, setApplied] = useState<Record<string, string>>({})

  const query = useQuery({
    queryKey: ["api", "public-offices", applied],
    queryFn: () => apiClient.publicOffices(applied),
    staleTime: 15_000,
  })

  const errorReason =
    query.error instanceof ApiUnreachable
      ? "API transport unavailable — roster/coverage reads need a running stack."
      : query.error instanceof ApiError
        ? `API error ${query.error.status}: ${query.error.detail}`
        : null

  return (
    <ViewPage>
      <PageHeader
        title="Public offices"
        description="Roster coverage, snapshots and officeholder members read from the API (BE-56 supporting surface)"
      />

      <Region spacing="sm">
        <form
          className="flex flex-wrap items-end gap-3"
          aria-label="Roster filters"
          onSubmit={(event) => {
            event.preventDefault()
            const next: Record<string, string> = {}
            if (scope.trim()) next.scope = scope.trim()
            if (term.trim()) next.term = term.trim()
            if (limit !== 200) next.limit = String(limit)
            setApplied(next)
          }}
          onReset={() => {
            setScope("")
            setTerm("")
            setLimit(200)
            setApplied({})
          }}
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="offices-scope" className="text-xs font-medium">Scope code</label>
            <Input
              id="offices-scope"
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              placeholder="all scopes"
              className="h-8 w-40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="offices-term" className="text-xs font-medium">Term</label>
            <Input
              id="offices-term"
              value={term}
              onChange={(event) => setTerm(event.target.value)}
              placeholder="any term"
              className="h-8 w-40"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="offices-limit" className="text-xs font-medium">Member limit</label>
            <select
              id="offices-limit"
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="border-border bg-background h-8 w-28 rounded-md border px-2 text-xs"
            >
              <option value={50}>50</option>
              <option value={200}>200</option>
              <option value={1000}>1000</option>
            </select>
          </div>
          <Button type="submit" size="sm">Apply filters</Button>
          <Button type="reset" size="sm" variant="ghost">Clear</Button>
        </form>
      </Region>

      <Region spacing="sm">
        {query.isPending ? <RegionSkeleton rows={5} /> : null}
        {query.isError ? (
          <RegionError detail={errorReason ?? String(query.error)} onRetry={() => void query.refetch()} />
        ) : null}
        {query.data ? <OfficesResponsePanels data={query.data} /> : null}
      </Region>
    </ViewPage>
  )
}

function OfficesResponsePanels({ data }: { data: OfficesResponse }) {
  const members = data.members as Record<string, unknown>[]
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2" aria-label="Roster summary">
        <Badge variant={data.coverage_status === "reconciled" ? "success-light" : "warning-light"}>
          coverage {data.coverage_status}
        </Badge>
        <Badge variant="outline">{data.scopes.length} scopes</Badge>
        <Badge variant="outline">{members.length} members</Badge>
        {data.truncated ? (
          <Badge variant="warning-light">truncated at the response limit</Badge>
        ) : null}
      </div>

      <section aria-label="Scope coverage">
        <p className="mb-1 text-xs font-semibold">Scope coverage</p>
        {data.scopes.length === 0 ? (
          <EmptyNote>No scopes reported.</EmptyNote>
        ) : (
          <ScopesTable scopes={data.scopes} />
        )}
      </section>

      <section aria-label="Roster members">
        <p className="mb-1 text-xs font-semibold">Members</p>
        {members.length === 0 ? (
          <EmptyNote>
            No members for the current scope/time/term filters.
            {data.diagnosis.length > 0 ? (
              <ul className="mt-1 list-disc ps-4 text-start">
                {data.diagnosis.map((line, index) => (
                  <li key={index}>{line}</li>
                ))}
              </ul>
            ) : null}
          </EmptyNote>
        ) : (
          <MembersTable data={members} />
        )}
        {data.truncated ? (
          <p className="text-muted-foreground mt-2 text-xs">
            The member list is truncated at the API result limit; unused member counts remain
            visible in the scope coverage above.
          </p>
        ) : null}
      </section>

      <section aria-label="Response diagnosis">
        <p className="mb-1 text-xs font-semibold">Diagnosis</p>
        {data.diagnosis.length === 0 ? (
          <EmptyNote>No diagnosis entries in this response.</EmptyNote>
        ) : (
          <ul className="list-disc ps-5 text-xs">
            {data.diagnosis.map((line, index) => (
              <li key={index}>{line}</li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

/** Status semantics come from the API; display names only, never approve. */
function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "failed"
      ? "destructive-light"
      : status === "partial"
        ? "warning-light"
        : status === "reconciled"
          ? "success-light"
          : status === "missing"
            ? "destructive-light"
            : "outline"
  return <Badge variant={variant}>{status}</Badge>
}

function ScopesTable({ scopes }: { scopes: ScopeCoverage[] }) {
  const columns = useMemo<ColumnDef<DataGridFeatures, ScopeCoverage>[]>(
    () => [
      {
        accessorKey: "scope",
        id: "scope",
        header: ({ column }) => <DataGridColumnHeader title="Scope" column={column} />,
        cell: ({ row }) => <span className="text-xs font-medium">{row.original.scope}</span>,
        size: 90,
      },
      {
        accessorKey: "institution",
        id: "institution",
        header: ({ column }) => <DataGridColumnHeader title="Institution" column={column} />,
        cell: ({ row }) => <span className="text-xs">{row.original.institution}</span>,
        size: 220,
      },
      {
        accessorKey: "status",
        id: "status",
        header: ({ column }) => <DataGridColumnHeader title="Status" column={column} />,
        cell: ({ row }) => <StatusBadge status={row.original.status} />,
        size: 110,
      },
      {
        accessorKey: "observed_at",
        id: "observed_at",
        header: ({ column }) => <DataGridColumnHeader title="Observed" column={column} />,
        cell: ({ row }) => (
          <span className="text-muted-foreground text-xs tabular-nums">
            {row.original.observed_at ?? "unknown"}
          </span>
        ),
        size: 170,
      },
      {
        accessorKey: "term",
        id: "term",
        header: ({ column }) => <DataGridColumnHeader title="Term" column={column} />,
        cell: ({ row }) => <span className="text-xs">{row.original.term ?? "unknown"}</span>,
        size: 110,
      },
      {
        accessorKey: "expected",
        id: "expected",
        header: ({ column }) => <DataGridColumnHeader title="Expected" column={column} />,
        cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.expected ?? "unknown"}</span>,
        meta: { headerClassName: "text-end", cellClassName: "text-end" },
        size: 85,
      },
      {
        accessorKey: "loaded",
        id: "loaded",
        header: ({ column }) => <DataGridColumnHeader title="Loaded" column={column} />,
        cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.loaded}</span>,
        meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
        size: 80,
      },
      {
        accessorKey: "distinct_persons",
        id: "persons",
        header: ({ column }) => <DataGridColumnHeader title="Persons" column={column} />,
        cell: ({ row }) => <span className="text-xs tabular-nums">{row.original.distinct_persons}</span>,
        meta: { headerClassName: "text-end", cellClassName: "text-end tabular-nums" },
        size: 80,
      },
      {
        accessorKey: "unresolved",
        id: "unresolved",
        header: ({ column }) => <DataGridColumnHeader title="Unresolved" column={column} />,
        cell: ({ row }) =>
          row.original.unresolved > 0 ? (
            <Badge variant="warning-light">{row.original.unresolved}</Badge>
          ) : (
            <span className="text-muted-foreground text-xs">0</span>
          ),
        meta: { headerClassName: "text-end", cellClassName: "text-end" },
        size: 95,
      },
      {
        accessorKey: "failed_rows",
        id: "failed",
        header: ({ column }) => <DataGridColumnHeader title="Failed rows" column={column} />,
        cell: ({ row }) =>
          row.original.failed_rows === null ? (
            <span className="text-muted-foreground text-xs">unknown</span>
          ) : row.original.failed_rows > 0 ? (
            <Badge variant="destructive-light">{row.original.failed_rows}</Badge>
          ) : (
            <span className="text-muted-foreground text-xs">0</span>
          ),
        meta: { headerClassName: "text-end", cellClassName: "text-end" },
        size: 95,
      },
      {
        accessorKey: "stale",
        id: "stale",
        header: ({ column }) => <DataGridColumnHeader title="Stale" column={column} />,
        cell: ({ row }) =>
          row.original.stale === null ? (
            <span className="text-muted-foreground text-xs">unknown</span>
          ) : row.original.stale ? (
            <Badge variant="warning-light">stale</Badge>
          ) : (
            <span className="text-muted-foreground text-xs">fresh</span>
          ),
        size: 80,
      },
      {
        accessorKey: "diagnosis",
        id: "diagnosis",
        header: ({ column }) => <DataGridColumnHeader title="Diagnosis" column={column} />,
        cell: ({ row }) => (
          <span className="text-muted-foreground text-xs">{row.original.diagnosis.join(" · ")}</span>
        ),
        size: 300,
      },
    ],
    [],
  )
  return (
    <DataTable
      data={scopes}
      columns={columns}
      pageSize={12}
      getRowId={(row) => row.scope}
      initialSorting={[{ id: "scope", desc: false }]}
    />
  )
}

/** Display value rendering: unknown stays unknown, lists show counts, links
 *  navigate through the generic entity view. */
function MemberText({ value, unknown }: { value: unknown; unknown?: boolean }) {
  if (value === null || value === undefined || value === "" || unknown) {
    return <span className="text-muted-foreground text-xs">unknown</span>
  }
  if (Array.isArray(value)) {
    return <span className="text-xs tabular-nums">{value.length}</span>
  }
  return <span className="text-xs">{String(value)}</span>
}

function MembersTable({ data }: { data: Record<string, unknown>[] }) {
  const columns = useMemo<ColumnDef<DataGridFeatures, Record<string, unknown>>[]>(() => {
    const text: ColumnDef<DataGridFeatures, Record<string, unknown>>[] = []
    const add = (key: string, title: string, size = 130, numeric = false) => {
      text.push({
        accessorFn: (row) => memberSortValue(row, key),
        id: key,
        header: ({ column }) => <DataGridColumnHeader title={title} column={column} />,
        cell: ({ row }) => <MemberText value={row.original[key]} />,
        size,
        meta: numeric
          ? { headerClassName: "text-end", cellClassName: "text-end" }
          : undefined,
      })
    }
    text.push({
      accessorFn: (row) => memberSortValue(row, "person_label"),
      id: "person",
      header: ({ column }) => <DataGridColumnHeader title="Individual" column={column} />,
      cell: ({ row }) => {
        const personId = typeof row.original.person_id === "string" ? row.original.person_id : null
        const label =
          typeof row.original.person_label === "string" && row.original.person_label
            ? row.original.person_label
            : ((typeof row.original.name === "string" && row.original.name
                ? row.original.name
                : null) ??
              (typeof row.original.external_id === "string" ? row.original.external_id : ""))
        return personId ? (
          <Link
            to={`/entity/${encodeURIComponent(personId)}`}
            className="hover:text-primary text-xs font-medium underline-offset-2 hover:underline"
          >
            {label || personId}
          </Link>
        ) : (
          <span className="text-xs">{label}</span>
        )
      },
      size: 200,
    })
    add("external_id", "External ID", 190)
    add("role", "Role", 100)
    add("party_label", "Party", 130)
    add("group_label", "Group", 130)
    add("represented_land", "Land", 110)
    add("constituency", "Constituency", 150)
    add("term", "Term", 100)
    add("mandate_kind", "Mandate", 120)
    add("profile_member_class", "Class", 90)
    add("service_start", "Service start", 170)
    add("service_end", "Service end", 170)
    add("service_precision", "Date precision", 110)
    text.push({
      accessorFn: (row) => memberSortValue(row, "conflicts"),
      id: "conflicts",
      header: ({ column }) => <DataGridColumnHeader title="Conflicts" column={column} />,
      cell: ({ row }) => {
        const conflicts = row.original.conflicts
        const count = Array.isArray(conflicts) ? conflicts.length : 0
        return count > 0 ? (
          <Badge variant="destructive-light">{count}</Badge>
        ) : (
          <span className="text-muted-foreground text-xs">0</span>
        )
      },
      size: 100,
      meta: { headerClassName: "text-end", cellClassName: "text-end" },
    })
    return text
  }, [])
  return (
    <DataTable
      data={data}
      columns={columns}
      pageSize={12}
      getRowId={(row) => String(row.external_id ?? row.person_id ?? "")}
      initialSorting={[{ id: "person", desc: false }]}
    />
  )
}

/** Sorting key: strings sort as strings, missing values sort last as "" and
 *  list values sort by length so counts order naturally. */
function memberSortValue(row: Record<string, unknown>, key: string): string | number {
  const value = row[key]
  if (value === null || value === undefined) return ""
  if (Array.isArray(value)) return value.length
  if (typeof value === "number") return value
  return String(value)
}
