// @vitest-environment jsdom
import type { PropsWithChildren } from "react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { act, cleanup, renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { apiClient, launcherApi } from "@/api/index"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { useSession } from "@/state/session"
import { useConnectionSync } from "../use-connection"

const healthy = { status: "ok", neo4j: true, ontology_version: "fixture" } as const
let client: QueryClient
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  useSession.setState({ reachability: "unknown", health: null, errorDetail: null, tokenRequired: false })
  vi.spyOn(apiClient, "health").mockResolvedValue({ ...healthy })
  vi.spyOn(launcherApi, "session").mockResolvedValue({ token_kind: "operator", profile: null, base_url: "http://127.0.0.1:8000" })
  vi.spyOn(launcherApi, "profiles").mockResolvedValue([])
  vi.spyOn(launcherApi, "activeProfile").mockResolvedValue({ active: null })
})
afterEach(() => { cleanup(); client.clear(); vi.restoreAllMocks() })

it.each([
  ["transport outage", new ApiUnreachable()],
  ["expired credential", new ApiError(401, "Credential expired")],
])("recovers from %s when the healthy payload is structurally unchanged", async (_name, failure) => {
  const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  renderHook(() => useConnectionSync(), { wrapper })
  await waitFor(() => expect(useSession.getState().reachability).toBe("reachable"))
  const original = client.getQueryData(["api", "health"])
  await act(async () => {
    await client.fetchQuery({ queryKey: ["api", "health"], queryFn: async () => { throw failure }, retry: false, staleTime: 0 }).catch(() => undefined)
  })
  await waitFor(() => expect(useSession.getState().reachability).toBe("unreachable"))
  expect(useSession.getState().tokenRequired).toBe(failure instanceof ApiError)
  await act(async () => {
    await client.fetchQuery({ queryKey: ["api", "health"], queryFn: async () => ({ ...healthy }), retry: false, staleTime: 0 })
  })
  expect(client.getQueryData(["api", "health"])).toBe(original)
  await waitFor(() => expect(useSession.getState().reachability).toBe("reachable"))
  expect(useSession.getState().errorDetail).toBeNull()
  expect(useSession.getState().tokenRequired).toBe(false)
})
