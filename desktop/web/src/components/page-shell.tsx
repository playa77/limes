// src/components/page-shell.tsx
// Shared page furniture: the header pattern (title + 1-clause description
// left, actions right) and the three data-region states (loading skeleton in
// the real layout, Empty with one action, inline error with Retry).

import type { ReactNode } from "react"
import { Frame, FrameHeader, FramePanel, FrameTitle, FrameDescription } from "@/components/reui/frame"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string
  description?: string
  actions?: ReactNode
  className?: string
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="min-w-0">
        <h1 className="text-base font-semibold tracking-tight">{title}</h1>
        {description ? (
          <p className="text-muted-foreground mt-0.5 text-xs">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}

export function ViewPage({ children }: { children: ReactNode }) {
  return <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 py-6">{children}</div>
}

/** A data region: one Frame block with an optional header and one body panel. */
export function Region({
  title,
  description,
  actions,
  children,
  className,
  spacing = "default",
  dense = false,
}: {
  title?: string
  description?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  spacing?: "xs" | "sm" | "default" | "lg"
  dense?: boolean
}) {
  return (
    <Frame spacing={spacing} dense={dense} className={cn("shadow-lifted-sm", className)}>
      {title ? (
        <FrameHeader>
          <FrameTitle>{title}</FrameTitle>
          {description ? <FrameDescription>{description}</FrameDescription> : null}
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </FrameHeader>
      ) : null}
      <FramePanel>{children}</FramePanel>
    </Frame>
  )
}

export function RegionSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2 py-1">
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-8 w-full" />
      ))}
    </div>
  )
}

export function RegionError({
  detail,
  onRetry,
}: {
  detail: string
  onRetry: () => void
}) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2"
    >
      {/* API error bodies are diagnostic signal: verbatim, no rephrasing. */}
      <p className="text-destructive-foreground min-w-0 flex-1 text-xs break-words">{detail}</p>
      <Button size="xs" variant="outline" onClick={onRetry}>
        Retry
      </Button>
    </div>
  )
}

export function EmptyNote({ children }: { children: ReactNode }) {
  return <p className="text-muted-foreground px-1 py-4 text-xs">{children}</p>
}
