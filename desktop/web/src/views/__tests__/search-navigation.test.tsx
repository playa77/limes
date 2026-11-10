// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router"
import { apiClient } from "@/api/index"
import { SearchView } from "../search-view"

function SearchRoute() {
  const location = useLocation()
  return <>
    <SearchView />
    <Link to="/search?q=Beta&from=header">Header navigation</Link>
    <output aria-label="Route query">{location.search}</output>
  </>
}

beforeEach(() => vi.spyOn(apiClient, "search").mockResolvedValue([]))
afterEach(() => { cleanup(); vi.restoreAllMocks() })

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/search?q=Alpha"]}>
    <Routes><Route path="/search" element={<SearchRoute />} /></Routes>
  </MemoryRouter></QueryClientProvider>)
}

it("uses a new header/URL query while the search route is already mounted", async () => {
  mount()
  await waitFor(() => expect(apiClient.search).toHaveBeenCalledWith("Alpha", null, 50))
  fireEvent.click(screen.getByRole("link", { name: "Header navigation" }))
  expect((screen.getByRole("combobox") as HTMLInputElement).value).toBe("Beta")
  await waitFor(() => expect(apiClient.search).toHaveBeenCalledWith("Beta", null, 50))
})

it("debounces requests while keeping typed text and the URL consistent", async () => {
  mount()
  const input = screen.getByRole("combobox")
  fireEvent.change(input, { target: { value: "B" } })
  fireEvent.change(input, { target: { value: "Beta" } })
  await waitFor(() => expect(apiClient.search).toHaveBeenCalledWith("Beta", null, 50))
  expect(apiClient.search).not.toHaveBeenCalledWith("B", null, 50)
  expect(screen.getByLabelText("Route query").textContent).toContain("q=Beta")
})
