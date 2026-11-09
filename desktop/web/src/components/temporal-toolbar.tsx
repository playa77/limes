// src/components/temporal-toolbar.tsx
// DC-14 shared temporal visibility: independent validity bounds and
// belief-as-of filtering applied by every graph pane. Invalid ranges are
// rejected inline; unknown timestamps stay unknown.

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useSession } from "@/state/session"
import { EMPTY_TEMPORAL, instantOf } from "@/state/temporal"
import type { TemporalFilter } from "@/state/temporal"

export function TemporalToolbar({ currencyWarn = false }: { currencyWarn?: boolean }) {
  const filter = useSession((s) => s.temporalFilter)
  const setFilter = useSession((s) => s.setTemporalFilter)
  const [from, setFrom] = useState(filter.validity_from ?? "")
  const [to, setTo] = useState(filter.validity_to ?? "")
  const [belief, setBelief] = useState(filter.belief_as_of ?? "")
  const [error, setError] = useState<string | null>(null)

  function apply() {
    const validityFrom = from.trim() === "" ? null : from.trim()
    const validityTo = to.trim() === "" ? null : to.trim()
    const beliefAsOf = belief.trim() === "" ? null : belief.trim()
    const lower = validityFrom === null ? null : instantOf(validityFrom)
    const upper = validityTo === null ? null : instantOf(validityTo, { endOfDay: true })
    const beliefInstant = beliefAsOf === null ? null : instantOf(beliefAsOf, { endOfDay: true })
    if (validityFrom !== null && lower === null) {
      setError("Validity from is not a parseable ISO instant.")
      return
    }
    if (validityTo !== null && upper === null) {
      setError("Validity to is not a parseable ISO instant.")
      return
    }
    if (lower !== null && upper !== null && lower > upper) {
      setError("Validity from is after validity to — the range is rejected.")
      return
    }
    if (beliefAsOf !== null && beliefInstant === null) {
      setError("Belief-as-of is not a parseable ISO instant.")
      return
    }
    setError(null)
    const next: TemporalFilter = {
      validity_from: validityFrom,
      validity_to: validityTo,
      belief_as_of: beliefAsOf,
    }
    setFilter(next)
  }

  return (
    <form
      className="flex flex-wrap items-end gap-2"
      aria-label="Temporal filter"
      onSubmit={(event) => {
        event.preventDefault()
        apply()
      }}
    >
      <div className="flex flex-col gap-0.5">
        <Label htmlFor="validity-from" className="text-[11px]">
          validity from
        </Label>
        <Input
          id="validity-from"
          value={from}
          onChange={(event) => setFrom(event.target.value)}
          placeholder="2020-01-01"
          className="h-7 w-36 font-mono text-xs"
        />
      </div>
      <div className="flex flex-col gap-0.5">
        <Label htmlFor="validity-to" className="text-[11px]">
          validity to
        </Label>
        <Input
          id="validity-to"
          value={to}
          onChange={(event) => setTo(event.target.value)}
          placeholder="2026-12-31"
          className="h-7 w-36 font-mono text-xs"
        />
      </div>
      <div className="flex flex-col gap-0.5">
        <Label htmlFor="belief-as-of" className="text-[11px]">
          belief as-of
        </Label>
        <Input
          id="belief-as-of"
          value={belief}
          onChange={(event) => setBelief(event.target.value)}
          placeholder="2024-06-01"
          className="h-7 w-36 font-mono text-xs"
        />
      </div>
      <Button type="submit" size="sm" variant="outline">
        Apply
      </Button>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        onClick={() => {
          setFrom("")
          setTo("")
          setBelief("")
          setError(null)
          setFilter({ ...EMPTY_TEMPORAL })
        }}
      >
        Clear
      </Button>
      {error ? (
        <p role="alert" className="text-destructive-foreground w-full text-xs">
          {error}
        </p>
      ) : null}
      {currencyWarn && filter.belief_as_of !== null ? (
        <p className="text-muted-foreground w-full text-xs">
          Retained result redraws with the filters; the filter never mutates history.
        </p>
      ) : null}
    </form>
  )
}
