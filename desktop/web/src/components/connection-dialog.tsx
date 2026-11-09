// src/components/connection-dialog.tsx
// Connection profiles (FR-DC-001/003) and the session token. Profiles carry
// names and URLs only; the token goes to the launcher once and stays in
// launcher memory for the session — it is never persisted and never returned.

import { useEffect, useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/reui/badge"
import {
  useProfileMutations,
  useProfiles,
  useSessionDescriptor,
  useSubmitToken,
} from "@/hooks/use-connection"
import { useSession } from "@/state/session"

export function ConnectionDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const profiles = useProfiles()
  const session = useSessionDescriptor()
  const activeProfile = useSession((s) => s.activeProfile)
  const tokenRequired = useSession((s) => s.tokenRequired)
  const { save, activate, remove } = useProfileMutations()
  const submitToken = useSubmitToken()

  const [newName, setNewName] = useState("")
  const [newUrl, setNewUrl] = useState("http://127.0.0.1:8000")
  const [token, setToken] = useState("")

  useEffect(() => {
    if (!open) {
      setToken("")
    }
  }, [open])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Connection</DialogTitle>
          <DialogDescription>
            Profiles store names and URLs only. Tokens stay in launcher session memory and never
            touch persistent storage.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-4">
          <section aria-label="Connection profiles" className="flex flex-col gap-2">
            <p className="text-xs font-medium">Profiles</p>
            {profiles.isLoading ? (
              <p className="text-muted-foreground text-xs">Loading profiles…</p>
            ) : null}
            {profiles.isError ? (
              <p className="text-destructive-foreground text-xs" role="alert">
                The launcher is unavailable; profiles cannot be read.
              </p>
            ) : null}
            {(profiles.data?.profiles.length ?? 0) === 0 && profiles.isSuccess ? (
              <p className="text-muted-foreground text-xs">
                No profiles yet — add one below.
              </p>
            ) : null}
            <ul className="flex flex-col gap-1">
              {(profiles.data?.profiles ?? []).map((profile) => (
                <li
                  key={profile.name}
                  className="flex items-center justify-between gap-2 rounded-md border px-2 py-1.5"
                >
                  <div className="min-w-0">
                    <span className="text-xs font-medium">{profile.name}</span>
                    <span className="text-muted-foreground block truncate text-xs">
                      {profile.base_url}
                    </span>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5">
                    {activeProfile === profile.name ? (
                      <Badge variant="primary-light">active</Badge>
                    ) : (
                      <Button
                        size="xs"
                        variant="outline"
                        onClick={() => activate.mutate(profile.name)}
                      >
                        Use
                      </Button>
                    )}
                    <Button
                      size="xs"
                      variant="ghost"
                      onClick={() => remove.mutate(profile.name)}
                      aria-label={`Delete profile ${profile.name}`}
                    >
                      Delete
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          <form
            aria-label="Add connection profile"
            className="grid grid-cols-1 gap-2 sm:grid-cols-[8rem,1fr,auto]"
            onSubmit={(event) => {
              event.preventDefault()
              const name = newName.trim()
              if (name === "" || newUrl.trim() === "") return
              save.mutate(
                { name, baseUrl: newUrl.trim() },
                { onSuccess: () => setNewName("") },
              )
            }}
          >
            <div className="flex flex-col gap-1">
              <Label htmlFor="profile-name" className="sr-only">
                Profile name
              </Label>
              <Input
                id="profile-name"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="name"
                className="h-8"
              />
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="profile-url" className="sr-only">
                Base URL
              </Label>
              <Input
                id="profile-url"
                value={newUrl}
                onChange={(event) => setNewUrl(event.target.value)}
                placeholder="http://127.0.0.1:8000"
                className="h-8"
                inputMode="url"
              />
            </div>
            <Button type="submit" size="sm" variant="outline" disabled={save.isPending}>
              Add
            </Button>
          </form>

          <section aria-label="Session token" className="flex flex-col gap-2">
            <DialogHeader>
              <DialogTitle className="text-xs">Session credential</DialogTitle>
              <DialogDescription className="text-xs">
                {tokenRequired
                  ? "The API rejected the current credential. Paste a token below to connect this session."
                  : session.data?.token_kind === "operator"
                    ? "An operator credential is active in this session (backup can be submitted)."
                    : session.data?.token_kind === "api"
                      ? "A consumer credential is active in this session."
                      : "No credential in this session yet."}
              </DialogDescription>
            </DialogHeader>
            <form
              className="grid grid-cols-[1fr,auto] items-end gap-2"
              onSubmit={(event) => {
                event.preventDefault()
                if (token.trim() === "") return
                submitToken.mutate(token, { onSuccess: () => setToken("") })
              }}
            >
              <div className="flex flex-col gap-1">
                <Label htmlFor="session-token" className="text-xs">
                  API or operator token (session only)
                </Label>
                <Input
                  id="session-token"
                  type="password"
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  autoComplete="off"
                  className="h-8 font-mono"
                />
              </div>
              <Button type="submit" size="sm" disabled={submitToken.isPending}>
                Connect
              </Button>
            </form>
          </section>
        </div>

        <DialogFooter>
          <p className="text-muted-foreground text-xs">
            Remote access uses HTTPS or a loopback SSH tunnel; the launcher binds loopback only.
          </p>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
