// src/views/news-document-view.tsx
// The immutable evidence bundle behind a dispatch/document key (AC-DC-8):
// the API's record plus its evidence rows; archived text that is absent
// stays visibly absent.

import { useParams, Link } from "react-router"
import { useQuery } from "@tanstack/react-query"
import { apiClient } from "@/api/index"
import { PageHeader, Region, RegionError, RegionSkeleton, ViewPage } from "@/components/page-shell"
import { Badge } from "@/components/reui/badge"

export function NewsDocumentView() {
  const { key = "" } = useParams()
  const document = useQuery({
    queryKey: ["api", "news", "documents", key],
    queryFn: () => apiClient.newsDocument(key),
    enabled: key !== "",
    retry: 1,
  })

  return (
    <ViewPage>
      <PageHeader
        title="Article record"
        description={`Dispatch record and evidence for ${key || "—"}`}
        actions={
          <Link to="/news/claims" className="text-primary text-xs underline">
            Back to claims
          </Link>
        }
      />
      {key === "" ? (
        <Region>
          <p className="text-muted-foreground text-xs">No document key.</p>
        </Region>
      ) : document.isPending ? (
        <Region title="Record">
          <RegionSkeleton rows={6} />
        </Region>
      ) : document.isError ? (
        <Region>
          <RegionError detail={document.error.message} onRetry={() => void document.refetch()} />
        </Region>
      ) : (
        <>
          <Region spacing="sm" title="Record">
            <dl className="grid grid-cols-[minmax(8rem,12rem),minmax(0,1fr)] gap-x-3 gap-y-1.5 text-xs">
              {Object.entries(document.data).map(([name, value]) => (
                <Field key={name} name={name} value={value} />
              ))}
            </dl>
          </Region>
          <Region spacing="sm" title="Evidence" description="Archived excerpts/spans behind the dispatch">
            {Array.isArray(document.data.evidence) && document.data.evidence.length === 0 ? (
              <p className="text-muted-foreground text-xs">
                No archived evidence rows — a report URL without archived text is a coverage gap,
                not fabricated evidence.
              </p>
            ) : null}
            <ul className="flex flex-col gap-2">
              {(Array.isArray(document.data.evidence) ? document.data.evidence : []).map(
                (row, index) => (
                  <li key={index} className="rounded-md border p-2 text-xs">
                    <Badge variant="outline">{String(typeof row)}</Badge>
                    <pre className="max-h-40 overflow-auto">
                      {JSON.stringify(row, null, 2)}
                    </pre>
                  </li>
                ),
              )}
            </ul>
          </Region>
        </>
      )}
    </ViewPage>
  )
}

function Field({ name, value }: { name: string; value: unknown }) {
  return (
    <>
      <dt className="text-muted-foreground">{name}</dt>
      <dd className="break-words">
        {value === null || value === undefined || value === "" ? (
          <span className="text-muted-foreground">unknown</span>
        ) : typeof value === "object" ? (
          <pre className="max-h-40 overflow-auto">{JSON.stringify(value, null, 2)}</pre>
        ) : (
          String(value)
        )}
      </dd>
    </>
  )
}
