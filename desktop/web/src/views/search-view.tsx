// src/views/search-view.tsx
// FR-DC-010/011: debounced free-text search with result-type badges from the
// response data, keyboard navigation (arrow keys + Enter), immediate
// navigation to the entity view.

import { useEffect, useRef, useState } from "react"
import { useNavigate, useSearchParams } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { useDebounce } from "@/hooks/use-debounce"
import { useSession } from "@/state/session"
import { PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

const DEBOUNCE_MS = 300

export function SearchView() {
  const [params, setParams] = useSearchParams()
  const initialQuery = params.get("q") ?? ""
  const [value, setValue] = useState(initialQuery)
  const debounced = useDebounce(value.trim(), DEBOUNCE_MS)
  const navigate = useNavigate()
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const reachability = useSession((s) => s.reachability)

  const trimmed = debounced

  useEffect(() => {
    if (trimmed !== initialQuery) {
      const next = new URLSearchParams(params)
      if (trimmed.length >= 2) next.set("q", trimmed)
      else next.delete("q")
      setParams(next, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trimmed])

  const query = useQuery({
    queryKey: ["api", "search", trimmed],
    queryFn: () => apiClient.search(trimmed, null, 50),
    enabled: trimmed.length >= 2,
  })

  const hits = query.data ?? []
  useEffect(() => {
    setCursor(0)
  }, [trimmed])

  function openHit(index: number) {
    const hit = hits[index]
    if (!hit) return
    if (hit.kind === "document") {
      navigate(`/news/documents/${encodeURIComponent(hit.id)}`)
    } else {
      navigate(`/entity/${encodeURIComponent(hit.id)}`)
    }
  }

  const loading = query.isFetching || query.isLoading

  return (
    <ViewPage>
      <PageHeader
        title="Search"
        description="Free-text search over entity names and aliases"
      />
      <Region spacing="sm">
        <div className="flex flex-col gap-2">
          <Input
            ref={inputRef}
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Search entities and documents…"
            aria-label="Search entities"
            role="combobox"
            aria-expanded="true"
            aria-controls="search-hits"
            aria-autocomplete="list"
            aria-activedescendant={hits[cursor] ? hitId(cursor) : undefined}
            className="h-10"
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault()
                setCursor((current) => Math.min(current + 1, hits.length - 1))
              } else if (event.key === "ArrowUp") {
                event.preventDefault()
                setCursor((current) => Math.max(current - 1, 0))
              } else if (event.key === "Enter") {
                event.preventDefault()
                openHit(cursor)
              }
            }}
          />
          <p className="text-muted-foreground text-xs">
            Arrow keys move, Enter opens. Results rank by the API's score.
          </p>
        </div>
      </Region>

      {trimmed.length < 2 ? (
        <Region>
          <p className="text-muted-foreground py-2 text-xs">Type at least two characters.</p>
        </Region>
      ) : loading ? (
        <Region title="Results">
          <RegionSkeleton rows={4} />
        </Region>
      ) : query.isError ? (
        <Region title="Results">
          <RegionError
            detail={
              query.error instanceof ApiError
                ? `API error ${query.error.status}: ${query.error.detail}`
                : query.error instanceof ApiUnreachable
                  ? "API transport unavailable — the LIMES stack is not reachable."
                  : "Search failed."
            }
            onRetry={() => void query.refetch()}
          />
        </Region>
      ) : hits.length === 0 ? (
        <Region title="Results">
          <p className="text-muted-foreground py-2 text-xs">
            No entity or document matched {`"${trimmed}"`}.
          </p>
        </Region>
      ) : (
        <Region title="Results" description={`${hits.length} hits`}>
          <ul id="search-hits" role="listbox" aria-label="Search results" className="flex flex-col">
            {hits.map((hit, index) => (
              <li key={`${hit.kind}:${hit.id}`} id={hitId(index)} role="option" aria-selected={index === cursor}>
                <button
                  type="button"
                  onMouseMove={() => setCursor(index)}
                  onClick={() => openHit(index)}
                  className={cn(
                    "hover:bg-muted grid w-full grid-cols-[auto,minmax(0,1fr),auto] items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors duration-200",
                    index === cursor && "bg-muted",
                  )}
                >
                  <Badge variant={hit.kind === "document" ? "info-light" : "primary-light"}>
                    {hit.kind}
                  </Badge>
                  <span className="truncate text-sm font-medium">{hit.label}</span>
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {hit.score.toFixed(3)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Region>
      )}
      {reachability === "unreachable" ? (
        <Button variant="outline" onClick={() => inputRef.current?.focus()}>
          Retry when the API returns
        </Button>
      ) : null}
    </ViewPage>
  )
}

function hitId(index: number): string {
  return `search-hit-${index}`
}
