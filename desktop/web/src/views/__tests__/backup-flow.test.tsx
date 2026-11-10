// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { operationJobFromApi } from "@/api/types"
import { useSession } from "@/state/session"
import { BackupView } from "../backup-view"

vi.mock("@/hooks/use-connection", () => ({ useCapabilityQuery: () => ({ data: { backup: true } }) }))
const dump = "limes-20261109T120000-abcdef.dump"
function job(id: string, status: string, output = "") {
  return operationJobFromApi({ job_id: id, request: { request_id: id, command: "backup" }, status, output, created_at: "2026-11-09T12:00:00Z", updated_at: "2026-11-09T12:00:00Z" })
}
beforeEach(() => {
  useSession.setState({ reachability: "reachable", backupRequestId: null })
  vi.spyOn(apiClient, "health").mockResolvedValue({ status: "ok", neo4j: true, ontology_version: "fixture" })
  vi.spyOn(apiClient, "submitBackup").mockImplementation(async (id) => job(id, "queued"))
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  return render(<QueryClientProvider client={client}><BackupView /></QueryClientProvider>)
}
async function submit() {
  fireEvent.click(screen.getByRole("button", { name: "Run backup" }))
  fireEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Run backup" }))
  await waitFor(() => expect(apiClient.submitBackup).toHaveBeenCalledTimes(1))
}
it("requires confirmed reachability before enabling a backup", () => {
  useSession.setState({ reachability: "unknown" })
  mount()
  expect((screen.getByRole("button", { name: "Run backup" }) as HTMLButtonElement).disabled).toBe(true)
})
it("reports the dump from the successful status response and verifies health", async () => {
  vi.spyOn(apiClient, "operationStatus").mockImplementation(async id => job(id, "succeeded", dump))
  mount(); await submit()
  await waitFor(() => expect(screen.getByText(/Backup complete; API healthy/).textContent).toContain(dump))
  expect(apiClient.health).toHaveBeenCalled()
})
it("treats PA-1 cancellation as terminal without resubmitting", async () => {
  vi.spyOn(apiClient, "operationStatus").mockImplementation(async id => job(id, "cancelled"))
  mount(); await submit()
  await screen.findByText(/Backup cancelled/)
  expect(apiClient.submitBackup).toHaveBeenCalledTimes(1)
})

it("retains the request across view remounts and only observes it", async () => {
  vi.spyOn(apiClient, "operationStatus").mockImplementation(async id => job(id, "succeeded", dump))
  const view = mount(); await submit()
  await screen.findByText(/Backup complete; API healthy/)
  const requestId = useSession.getState().backupRequestId
  view.unmount()
  mount()
  await screen.findByText(/Backup complete; API healthy/)
  expect(apiClient.operationStatus).toHaveBeenCalledWith(requestId)
  expect(apiClient.submitBackup).toHaveBeenCalledTimes(1)
})
