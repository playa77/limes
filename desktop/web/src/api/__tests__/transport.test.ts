import { afterEach, describe, expect, it, vi } from "vitest"
import { ApiClient } from "../client"
import { LauncherApi } from "../launcher"

afterEach(() => vi.unstubAllGlobals())

describe("browser fetch receiver", () => {
  it.each([
    ["API", () => new ApiClient().health(), "/api/health"],
    ["launcher", () => new LauncherApi().session(), "/session"],
  ] as const)("uses the global receiver for the default %s transport", async (_name, request, path) => {
    const calls: unknown[] = []
    // Chromium's native fetch requires the Window receiver. A permissive injected
    // mock (or Node's fetch) misses the Illegal invocation raised in the browser.
    vi.stubGlobal("fetch", function (this: unknown, input: unknown) {
      if (this !== globalThis) throw new TypeError("Illegal invocation")
      calls.push(input)
      return Promise.resolve(new Response(JSON.stringify({ status: "ok", neo4j: true, ontology_version: "fixture" })))
    })
    await expect(request()).resolves.toBeDefined()
    expect(calls).toEqual([path])
  })
})
