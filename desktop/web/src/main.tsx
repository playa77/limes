// src/main.tsx
// The launcher-served SPA entry: one query client for the apiClient/launcherApi
// singletons, one router for the rail routes. The canvas gradient tokens live
// in index.css; Inter Variable is bundled locally (no font CDN).

import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { RouterProvider } from "react-router"
import { router } from "@/routes"

import "@fontsource-variable/inter"
import "@/index.css"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Views opt into focused behaviors themselves (health polls every 15s,
      // ingest refreshes every 10s while visible); retries otherwise protect
      // against transport blips without hammering a degraded API.
      retry: 1,
      retryDelay: 2_000,
      refetchOnWindowFocus: false,
    },
  },
})

const root = document.getElementById("root")
if (!root) throw new Error("The launcher page has no #root container")

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
