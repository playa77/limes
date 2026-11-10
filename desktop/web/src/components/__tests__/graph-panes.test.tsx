// @vitest-environment jsdom
import { StrictMode } from "react"
import { afterEach, beforeEach, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { graphResultFromApi } from "@/api/types"
import { apiClient } from "@/api/index"
import { useSession } from "@/state/session"
import { EMPTY_TEMPORAL } from "@/state/temporal"
import { NetworkPane, TimelinePane } from "../graph-panes"

const mocks = vi.hoisted(() => ({
  cy: vi.fn(), plot: vi.fn(), purge: vi.fn(), on: vi.fn(),
  removeAllListeners: vi.fn(), handlers: new Map<string, (event: unknown) => void>(),
}))
vi.mock("cytoscape", () => ({ default: mocks.cy }))
vi.mock("plotly.js-dist-min", () => ({ default: { react: mocks.plot, purge: mocks.purge } }))

const node = (id: string) => ({ entity_id: id, type: "AardvarkSong", label: id, properties: {} })
const edge = (a: string, b: string, recorded: string) => ({
  subject_id: a, object_id: b, relation: "PURPLE_LADDER", recorded_at: recorded,
})
const bundle = { result: graphResultFromApi({
  nodes: [node("a"), node("b")], edges: [edge("a", "b", "2024-01-01")], counts: {},
}), coverage: null }
const instances: { destroy: ReturnType<typeof vi.fn> }[] = []

beforeEach(() => {
  vi.clearAllMocks(); mocks.handlers.clear(); instances.length = 0
  useSession.setState({ selection: "a", temporalFilter: { ...EMPTY_TEMPORAL } })
  mocks.cy.mockImplementation(() => {
    const instance = {
      on: vi.fn(), destroy: vi.fn(),
      nodes: () => ({ unselect: vi.fn() }),
      elements: () => ({ unselect: vi.fn() }),
      getElementById: () => ({ nonempty: () => true, select: vi.fn() }),
    }
    instances.push(instance)
    return instance
  })
  mocks.on.mockImplementation((name, handler) => mocks.handlers.set(name, handler))
  mocks.plot.mockImplementation(async (element: HTMLElement) => Object.assign(element, {
    on: mocks.on, removeAllListeners: mocks.removeAllListeners,
  }))
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it("selects the source from a Plotly emitter event, then removes its listener", async () => {
  const view = render(<TimelinePane bundle={bundle} />)
  await waitFor(() => expect(mocks.on).toHaveBeenCalledWith("plotly_click", expect.any(Function)))
  act(() => mocks.handlers.get("plotly_click")!({ points: [{ customdata: ["b", "2024-01-01"] }] }))
  expect(useSession.getState().selection).toBe("b")
  view.unmount()
  expect(mocks.removeAllListeners).toHaveBeenCalledWith("plotly_click")
})

it("does not create a network renderer after effect cleanup in StrictMode", async () => {
  const view = render(<StrictMode><NetworkPane bundle={bundle} /></StrictMode>)
  await waitFor(() => expect(mocks.cy).toHaveBeenCalled())
  expect(instances).toHaveLength(1)
  view.unmount()
  expect(instances[0].destroy).toHaveBeenCalledTimes(1)
})

it("applies belief time to expanded assertions as well as the original graph", async () => {
  const extra = graphResultFromApi({ nodes: [node("c")], edges: [edge("a", "c", "2025-01-01")], counts: {} })
  vi.spyOn(apiClient, "entityNeighbors").mockResolvedValue({
    entity: bundle.result.nodes[0], neighbors: [{ neighbor: extra.nodes[0], edge: extra.edges[0] }],
  })
  render(<NetworkPane bundle={bundle} />)
  fireEvent.click(screen.getByRole("button", { name: "Expand selected" }))
  await screen.findByText("3 nodes")
  act(() => useSession.getState().setTemporalFilter({ ...EMPTY_TEMPORAL, belief_as_of: "2024-06-01" }))
  await screen.findByText("2 nodes")
  expect(screen.getByText("1 edges")).toBeDefined()
})

it("reports a neighbor failure without discarding a previous expansion", async () => {
  const extra = graphResultFromApi({ nodes: [node("c")], edges: [edge("a", "c", "2024-01-01")], counts: {} })
  vi.spyOn(apiClient, "entityNeighbors")
    .mockResolvedValueOnce({ entity: bundle.result.nodes[0], neighbors: [{ neighbor: extra.nodes[0], edge: extra.edges[0] }] })
    .mockRejectedValueOnce(new Error("neighbors unavailable"))
  render(<NetworkPane bundle={bundle} />)
  fireEvent.click(screen.getByRole("button", { name: "Expand selected" }))
  await screen.findByText("3 nodes")
  fireEvent.click(screen.getByRole("button", { name: "Expand selected" }))
  expect((await screen.findByRole("alert")).textContent).toContain("neighbors unavailable")
  expect(screen.getByText("3 nodes")).toBeDefined()
})

it("shows a rendering error instead of leaving a silent blank timeline", async () => {
  mocks.plot.mockRejectedValueOnce(new Error("plot unavailable"))
  render(<TimelinePane bundle={bundle} />)
  expect((await screen.findByRole("alert")).textContent).toContain("plot unavailable")
})

it("does not carry an old expansion into a different query result", async () => {
  const extra = graphResultFromApi({ nodes: [node("c")], edges: [edge("a", "c", "2024-01-01")], counts: {} })
  vi.spyOn(apiClient, "entityNeighbors").mockResolvedValue({
    entity: bundle.result.nodes[0], neighbors: [{ neighbor: extra.nodes[0], edge: extra.edges[0] }],
  })
  const view = render(<NetworkPane bundle={bundle} />)
  fireEvent.click(screen.getByRole("button", { name: "Expand selected" }))
  await screen.findByText("3 nodes")
  view.rerender(<NetworkPane bundle={{ result: graphResultFromApi({ nodes: [node("z")], edges: [], counts: {} }), coverage: null }} />)
  await screen.findByText("1 nodes")
  expect(screen.getByText("0 edges")).toBeDefined()
})
