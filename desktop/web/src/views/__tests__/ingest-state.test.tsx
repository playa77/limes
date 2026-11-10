// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest"
import { cleanup, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { ingestRunFromApi } from "@/api/types"
import { IngestView } from "../ops-ingest-view"

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it("shows stale rate limiting even before a terminal error is counted", async () => {
  vi.spyOn(apiClient, "ingestStatus").mockResolvedValue([ingestRunFromApi({
    source_id: "ted", mode: "ingest", run_id: "blocked", started_at: "2026-11-10T12:00:00Z",
    finished_at: null, records_fetched: 0, nodes_created: 0, nodes_matched: 0,
    assertions_written: 0, assertions_skipped: 0, assertions_rejected: 0,
    documents_gated_out: 0, errors: 0, cost_eur: 0,
    state: "rate_limited", progress_stale: true, last_error: "HTTP 429",
  })])
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(<QueryClientProvider client={client}><IngestView /></QueryClientProvider>)
  expect((await screen.findByText(/rate limited/)).textContent)
    .toContain("no recent progress; incomplete")
  expect(screen.getByTitle("HTTP 429")).toBeTruthy()
  expect(screen.queryByText(/healthy/i)).toBeNull()
})
