// src/routes.tsx
// The route table mirrors the disabled-old-desktop navigation one-to-one. The
// launcher serves the built bundle and we use the browser history API with a
// server-side index.html fallback for deep links.

import { createBrowserRouter, Navigate } from "react-router"
import { AppShell } from "@/app/app-shell"

import { BackupView } from "@/views/backup-view"
import { DevelopmentsView } from "@/views/developments-view"
import { EntityView } from "@/views/entity-view"
import { HistoryView } from "@/views/history-view"
import { IngestView, LedgerView } from "@/views/ops-ingest-view"
import { PublicOfficesView } from "@/views/public-offices-view"
import { ReferencesView } from "@/views/ops-references-view"
import { NewsClaimsView } from "@/views/news-claims-view"
import { NewsDocumentView } from "@/views/news-document-view"
import { NewsInvestigationsView } from "@/views/news-investigations-view"
import { QueryBuilderView } from "@/views/query-builder-view"
import { QueryCypherView } from "@/views/query-cypher-view"
import { QueryNlView } from "@/views/query-nl-view"
import { MapView, NetworkView, TimelineView } from "@/views/viz-view"
import { SearchView } from "@/views/search-view"

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Navigate to="/search" replace /> },
      { path: "search", element: <SearchView /> },
      { path: "entity/:entityId", element: <EntityView /> },
      { path: "query/nl", element: <QueryNlView /> },
      { path: "query/builder", element: <QueryBuilderView /> },
      { path: "query/cypher", element: <QueryCypherView /> },
      { path: "history", element: <HistoryView /> },
      { path: "viz/network", element: <NetworkView /> },
      { path: "viz/map", element: <MapView /> },
      { path: "viz/timeline", element: <TimelineView /> },
      { path: "news/claims", element: <NewsClaimsView /> },
      { path: "news/investigations", element: <NewsInvestigationsView /> },
      { path: "news/developments", element: <DevelopmentsView /> },
      { path: "news/documents/:key", element: <NewsDocumentView /> },
      { path: "ops/ingest", element: <IngestView /> },
      { path: "ops/ledger", element: <LedgerView /> },
      { path: "ops/references", element: <ReferencesView /> },
      { path: "ops/offices", element: <PublicOfficesView /> },
      { path: "backup", element: <BackupView /> },
    ],
  },
])
