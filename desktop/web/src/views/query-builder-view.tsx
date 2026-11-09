// src/views/query-builder-view.tsx
// FR-DC-031: constructed entirely from GET /builder/schema — no ontology
// literals exist anywhere in this module. The refill semantics are the DC-14
// invariants implemented in src/state/builder.ts (relation change refills the
// admissible directions; a direction change keeps the relation; every refill
// recomputes the downstream suffix; submission revalidates every triple).

import { useEffect, useState } from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { toast } from "sonner"
import {
  buildSpec,
  createIndex,
  refreshFrom,
  schemaFromApi,
  DIRECTION_LABELS,
  type BuilderState,
  type HopState,
  type Schema,
} from "@/state/builder"
import { useSession } from "@/state/session"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { EmptyNote, PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"
import { QueryResultSurface } from "@/components/query-results"

export function QueryBuilderView() {
  const schema = useQuery({
    queryKey: ["api", "builder", "schema"],
    queryFn: () => apiClient.builderSchema(),
    // One fetch on first open only (lazy schema fetch, like the desktop).
    staleTime: Infinity,
    retry: 1,
  })
  const [state, setState] = useState<BuilderState | null>(null)
  const publish = useSession((s) => s.publish)
  const lastOutcome = useSession((s) => s.lastOutcome)

  const parsed: Schema | null = schema.data ? schemaFromApi(schema.data) : null
  const index = useMemoIndex(parsed)

  useEffect(() => {
    if (index !== null && state === null && parsed !== null) {
      setState(initialState(index, parsed))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, parsed])

  const run = useMutation({
    mutationFn: (spec: Parameters<typeof apiClient.queryBuilder>[0]) =>
      apiClient.queryBuilder(spec),
    onSuccess: (outcome) => {
      publish(outcome)
      toast.success("Builder query executed.")
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        toast.error(`API error ${error.status}`, { description: error.detail })
      } else if (error instanceof ApiUnreachable) {
        toast.error("API transport unavailable", { description: error.message })
      } else {
        toast.error("Builder query failed", { description: error.message })
      }
    },
  })

  if (schema.isPending) {
    return (
      <ViewPage>
        <PageHeader title="Query builder" description="Schema-driven hop construction" />
        <Region title="Schema">
          <RegionSkeleton rows={4} />
        </Region>
      </ViewPage>
    )
  }
  if (schema.isError || parsed === null || index === null || state === null) {
    return (
      <ViewPage>
        <PageHeader title="Query builder" description="Schema unavailable" />
        <Region>
          <RegionError
            detail={
              schema.error instanceof ApiError
                ? `API error ${schema.error.status}: ${schema.error.detail}`
                : "GET /builder/schema failed; the builder cannot be constructed without it."
            }
            onRetry={() => void schema.refetch()}
          />
        </Region>
      </ViewPage>
    )
  }

  const spec = buildSpec(index, state)

  function update(next: BuilderState) {
    setState(next)
  }

  return (
    <ViewPage>
      <PageHeader
        title="Query builder"
        description="Hops, relations and targets come from the schema admissibility only"
        actions={
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => update(addHop(index, state))}
            >
              Add hop
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={state.hops.length <= 1}
              onClick={() => {
                const hops = state.hops.slice(0, -1).map(cloneHop)
                update(refreshFrom(index, state.start_type, hops, hops.length, withAt(hops.length, true)))
              }}
            >
              Remove hop
            </Button>
          </div>
        }
      />
      <Region spacing="sm">
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            if (spec === null) return
            run.mutate(spec)
          }}
        >
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex flex-col gap-1">
              <Label className="text-xs">Start type</Label>
              <Select
                value={state.start_type ?? undefined}
                onValueChange={(value) => {
                  // A start-type change refills the first hop's relation and
                  // recomputes the whole chain while keeping selections that
                  // stay admissible (DC-14).
                  const hops = state.hops.map(cloneHop)
                  update(refreshFrom(index, value, hops, 0, withAt(hops.length, true, 0)))
                }}
              >
                <SelectTrigger size="sm" className="h-7 w-56" aria-label="Start type">
                  <SelectValue placeholder="Pick a start type" />
                </SelectTrigger>
                <SelectContent>
                  {parsed.entity_types.map((entry) => (
                    <SelectItem key={entry.name} value={entry.name}>
                      {entry.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" size="sm" disabled={spec === null || run.isPending}>
              {run.isPending ? "Running…" : "Run"}
            </Button>
          </div>

          <ol className="flex flex-col gap-3">
            {state.hops.map((hop, hopIndex) => (
              <li key={hopIndex} className="rounded-lg border p-2">
                <p className="text-muted-foreground mb-2 text-xs">
                  hop {hopIndex + 1}
                  {hopIndex > 0 ? " — chains off the previous target" : " — chains off the start type"}
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <RowSelect
                    id={`hop-${hopIndex}-relation`}
                    label="relation"
                    value={hop.relation}
                    options={hop.relations}
                    onChange={(value) => {
                      const relation = value ?? ""
                      const hops = state.hops.map(cloneHop)
                      hops[hopIndex].relation = relation || null
                      // A relation change recomputes admissible directions and
                      // the whole suffix, but does not re-pick the relation.
                      update(refreshFrom(index, state.start_type, hops, hopIndex, withAt(hops.length, false)))
                    }}
                  />
                  <RowSelect
                    id={`hop-${hopIndex}-direction`}
                    label="direction"
                    value={hop.direction}
                    labels={DIRECTION_LABELS}
                    options={hop.directions}
                    onChange={(value) => {
                      const direction = value as BuilderState["hops"][number]["direction"] | null
                      const hops = state.hops.map(cloneHop)
                      hops[hopIndex].direction = direction
                      // A direction change NEVER refills the relation (DC-14).
                      update(refreshFrom(index, state.start_type, hops, hopIndex, withAt(hops.length, false)))
                    }}
                  />
                  <RowSelect
                    id={`hop-${hopIndex}-target`}
                    label="target"
                    value={hop.target_type}
                    options={hop.targets}
                    onChange={(value) => {
                      const target = value ?? ""
                      const hops = state.hops.map(cloneHop)
                      hops[hopIndex].target_type = target || null
                      // A target change re-admissibilizes the next hop only.
                      update(refreshFrom(index, state.start_type, hops, hopIndex + 1, withAt(hops.length, true, hopIndex + 1)))
                    }}
                  />
                </div>
              </li>
            ))}
          </ol>
          {spec === null ? (
            <p className="text-muted-foreground text-xs">
              The chain is not yet a submittable spec: every hop must have an admissible
              relation/direction/target triple.
            </p>
          ) : (
            <p className="text-muted-foreground text-xs">
              {`Spec: ${spec.start_type}${spec.hops.map((hop) => ` → ${hop.relation} (${hop.direction}) → ${hop.target_type}`).join("")}`}
            </p>
          )}
        </form>
      </Region>

      {lastOutcome !== null ? (
        <Region
          spacing="sm"
          title="Outcome"
          description="Coverage attaches to the executed spec (AC-23); empty results carry the hop diagnosis."
        >
          <QueryResultSurface bundle={lastOutcome} />
        </Region>
      ) : (
        <Region>
          <EmptyNote>Run a builder spec to publish its outcome here.</EmptyNote>
        </Region>
      )}
    </ViewPage>
  )
}

// -- helpers (kept above React so the state machine stays testable) ---------

import { useMemo } from "react"

function useMemoIndex(schema: Schema | null) {
  return useMemo(() => (schema ? createIndex(schema) : null), [schema])
}

function initialState(
  index: NonNullable<ReturnType<typeof useMemoIndex>>,
  schema: Schema,
  startType?: string,
): BuilderState {
  const start = startType ?? schema.entity_types[0]?.name ?? null
  if (start === null) return { start_type: null, hops: [] }
  const hops = [emptyHop()]
  return refreshFrom(index, start, hops, 0)
}

function emptyHop(): HopState {
  return { relation: null, direction: null, target_type: null }
}

function cloneHop(hop: BuilderState["hops"][number]): BuilderState["hops"][number] {
  return {
    relation: hop.relation,
    direction: hop.direction,
    target_type: hop.target_type,
    relations: [...hop.relations],
    directions: [...hop.directions],
    targets: [...hop.targets],
  }
}

function addHop(
  index: NonNullable<ReturnType<typeof useMemoIndex>>,
  state: BuilderState,
): BuilderState {
  const hops = [...state.hops.map(cloneHop), emptyHop()]
  return refreshFrom(index, state.start_type, hops, hops.length - 1)
}

/** Relation-refill flags: `at` carries the acted-on hop's rule; downstream
 *  hops default to their refreshFrom semantics. */
function withAt(count: number, value: boolean, at: number = 0): (boolean | undefined)[] {
  return Array.from({ length: count }, (_, hopIndex) => (hopIndex === at ? value : undefined))
}

function RowSelect({
  id,
  label,
  value,
  options,
  labels,
  onChange,
}: {
  id: string
  label: string
  value: string | null
  options: string[]
  labels?: Record<string, string>
  onChange: (value: string | null) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <Label htmlFor={id} className="text-xs">
        {label}
      </Label>
      <Select
        value={value ?? undefined}
        onValueChange={(next) => onChange(next ?? null)}
        disabled={options.length === 0}
      >
        <SelectTrigger size="sm" id={id} className="h-7 w-44" aria-label={label}>
          <SelectValue placeholder={`Admissible ${label}`} />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {labels?.[option] ?? option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {options.length === 0 ? (
        <p className="text-muted-foreground text-[11px]">No admissible {label}.</p>
      ) : null}
    </div>
  )
}
