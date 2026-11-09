// src/app/app-shell.tsx
// The shared shell: skip link (keyboard order before the nav), header with
// the always-visible connection state, the persistent floating rail with
// grouped navigation, and the content column. The canvas gradient lives on
// <body>; surfaces float above it with the shared lifted shadow token.

import { useEffect, useState } from "react"
import { Link, NavLink, Outlet, useNavigate } from "react-router"
import { useDebounce } from "@/hooks/use-debounce"
import { useConnectionSync } from "@/hooks/use-connection"
import { useSession } from "@/state/session"
import { Badge } from "@/components/reui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ConnectionDialog } from "@/components/connection-dialog"
import { cn } from "@/lib/utils"
import {
  Activity,
  Archive,
  Bell,
  BookOpen,
  CircleHelp,
  Coins,
  Database,
  Route,
  Search,
  ShieldAlert,
  Table,
} from "lucide-react"

const RAIL_GROUPS = [
  {
    heading: "Investigate",
    items: [
      { to: "/search", label: "Search", icon: Search },
      { to: "/query/nl", label: "NL query", icon: CircleHelp },
      { to: "/query/builder", label: "Query builder", icon: Route },
      { to: "/query/cypher", label: "Cypher console", icon: BookOpen },
      { to: "/history", label: "History & saved", icon: Table },
    ],
  },
  {
    heading: "Visualize",
    items: [
      { to: "/viz/network", label: "Network", icon: Activity },
      { to: "/viz/map", label: "Map", icon: Database },
      { to: "/viz/timeline", label: "Timeline", icon: Bell },
    ],
  },
  {
    heading: "News",
    items: [
      { to: "/news/claims", label: "Claims", icon: ShieldAlert },
      { to: "/news/investigations", label: "Investigations", icon: Bell },
      { to: "/news/developments", label: "Developments", icon: Route },
    ],
  },
  {
    heading: "Operations",
    items: [
      { to: "/ops/ingest", label: "Ingest status", icon: Activity },
      { to: "/ops/ledger", label: "Cost ledger", icon: Coins },
      { to: "/ops/references", label: "Sources & ontology", icon: BookOpen },
      { to: "/ops/offices", label: "Public offices", icon: Archive },
      { to: "/backup", label: "Backup", icon: Database },
    ],
  },
]

export function AppShell() {
  useConnectionSync()
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState("")
  const debouncedQuery = useDebounce(searchValue.trim(), 300)
  const [connectOpen, setConnectOpen] = useState(false)

  // The header search stays the primary navigation instrument (FR-DC-011):
  // type, debounce, then jump to the full search view with the query.
  useEffect(() => {
    if (debouncedQuery.length >= 2) {
      const q = debouncedQuery
      setSearchValue("")
      navigate(`/search?q=${encodeURIComponent(q)}&from=header`)
    }
  }, [debouncedQuery, navigate])

  return (
    <div className="flex min-h-full flex-col">
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:top-3 focus-visible:left-3 focus-visible:z-50 focus-visible:rounded-md focus-visible:bg-primary focus-visible:px-3 focus-visible:py-1.5 focus-visible:text-primary-foreground"
      >
        Skip to main content
      </a>
      <header className="bg-card/80 shadow-lifted-sm sticky top-0 z-40 border-b backdrop-blur">
        <div className="mx-auto flex w-full max-w-[100rem] items-center gap-3 px-4 py-2">
          <Link to="/search" className="flex items-center gap-2 font-semibold tracking-tight">
            <span className="bg-primary size-6 rounded-md" aria-hidden="true" />
            LIMES Desktop
          </Link>
          <div className="w-64">
            <form
              onSubmit={(event) => event.preventDefault()}
              role="search"
              aria-label="Global entity search"
            >
              <Input
                value={searchValue}
                onChange={(event) => setSearchValue(event.target.value)}
                type="search"
                placeholder="Search entities…"
                aria-label="Search entities"
                className="h-8"
              />
            </form>
          </div>
          <div className="ms-auto flex items-center gap-2">
            <ConnectionStateBadge />
            <Button size="sm" variant="outline" onClick={() => setConnectOpen(true)}>
              Connection
            </Button>
          </div>
        </div>
      </header>
      <div className="mx-auto flex w-full max-w-[100rem] flex-1 gap-6 px-4">
        <nav
          aria-label="Main navigation"
          className="bg-card shadow-lifted sticky top-16 mt-4 hidden h-max w-52 shrink-0 flex-col gap-4 self-start rounded-xl border-y p-3 md:flex"
        >
          {RAIL_GROUPS.map((group) => (
            <div key={group.heading} className="flex flex-col gap-0.5">
              <p className="text-muted-foreground px-2 py-1 text-xs font-medium tracking-tight">
                {group.heading}
              </p>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  aria-current={undefined}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
                      isActive
                        ? "bg-muted text-foreground aria-current"
                        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      <item.icon className="size-4" aria-hidden="true" />
                      <span aria-current={isActive ? "location" : undefined}>{item.label}</span>
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <main id="main-content" className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>
      <ConnectionDialog open={connectOpen} onOpenChange={setConnectOpen} />
    </div>
  )
}

function ConnectionStateBadge() {
  const reachability = useSession((s) => s.reachability)
  const health = useSession((s) => s.health)
  const detail = useSession((s) => s.errorDetail)
  const title =
    reachability === "reachable"
      ? `API ${health?.status ?? "ok"} — Neo4j ${health?.neo4j ? "up" : "down"}, ontology ${health?.ontology_version ?? "?"}`
      : (detail ?? "Checking API reachability")
  if (reachability === "reachable") {
    return (
      <Badge variant="success-light" title={title}>
        API ok
      </Badge>
    )
  }
  if (reachability === "unreachable") {
    return (
      <Badge variant="destructive-light" title={title}>
        API unreachable
      </Badge>
    )
  }
  return (
    <Badge variant="outline" title={title}>
      checking…
    </Badge>
  )
}
