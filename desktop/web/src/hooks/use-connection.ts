// src/hooks/use-connection.ts
// Connection management (FR-DC-001..003): the launcher session, the profile
// store, and the always-visible health poll. A 401 from the API surfaces the
// token dialog; capabilities prove the operator credential (or its absence).

import { useEffect } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { ApiError, ApiUnreachable } from "@/api/errors"
import { apiClient, launcherApi } from "@/api/index"
import { useSession } from "@/state/session"

const HEALTH_POLL_MS = 15_000

export function useSessionDescriptor() {
  return useQuery({
    queryKey: ["launcher", "session"],
    queryFn: () => launcherApi.session(),
    retry: false,
    staleTime: 5_000,
  })
}

export function useProfiles() {
  const session = useSessionDescriptor()
  return useQuery({
    queryKey: ["launcher", "profiles"],
    queryFn: async () => {
      const [profiles, active] = await Promise.all([
        launcherApi.profiles(),
        launcherApi.activeProfile(),
      ])
      return { profiles, active: active.active }
    },
    enabled: !session.isError,
    staleTime: 2_000,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ["api", "health"],
    queryFn: () => apiClient.health(),
    refetchInterval: HEALTH_POLL_MS,
    refetchOnWindowFocus: true,
    retry: 1,
    retryDelay: 2_000,
    staleTime: 10_000,
  })
}

export function useCapabilities(enabled: boolean) {
  return useQuery({
    queryKey: ["api", "capabilities"],
    queryFn: () => apiClient.operationCapabilities(),
    enabled,
    staleTime: 30_000,
    retry: false,
  })
}

/** Publish query state into the session store exactly once per change. */
export function useConnectionSync(): void {
  const queryClient = useQueryClient()
  const setHealth = useSession((s) => s.setHealth)
  const setUnreachable = useSession((s) => s.setUnreachable)
  const setTokenRequired = useSession((s) => s.setTokenRequired)
  const setProfiles = useSession((s) => s.setProfiles)

  const profiles = useProfiles()
  const health = useHealth()

  useEffect(() => {
    if (profiles.data) setProfiles(profiles.data.profiles, profiles.data.active)
  }, [profiles.data, setProfiles])

  useEffect(() => {
    // Equal recovered payloads reuse their cached object; status still changes.
    if (health.isSuccess && health.data) {
      setHealth(health.data)
      setTokenRequired(false)
    }
  }, [health.data, health.isSuccess, setHealth, setTokenRequired])

  useEffect(() => {
    if (!health.isError) return
    const reason =
      health.error instanceof ApiUnreachable
        ? "API transport unavailable — is the LIMES stack running?"
        : health.error instanceof ApiError
          ? `API error ${health.error.status}: ${health.error.detail}`
          : "API unreachable"
    setUnreachable(reason)
    setTokenRequired(health.error instanceof ApiError && health.error.isUnauthorized)
  }, [health.isError, health.error, setUnreachable, setTokenRequired])

  useEffect(() => {
    if (health.isSuccess) {
      // Recovery: drop the stale capability answer so it re-proves itself.
      void queryClient.invalidateQueries({ queryKey: ["api", "capabilities"] })
    }
  }, [health.isSuccess, queryClient])
}

/** Capabilities only matter while the API answers; null means no operator
 *  credential (backup disabled with its precise reason, FR-DC-063). */
export function useCapabilityQuery() {
  const reachability = useSession((s) => s.reachability)
  return useCapabilities(reachability === "reachable")
}

/** Submitting a typed token to the launcher (session memory only). */
export function useSubmitToken() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (token: string) => launcherApi.setToken(token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["api", "health"] })
      void queryClient.invalidateQueries({ queryKey: ["launcher", "session"] })
    },
  })
}

/** Profile mutations: the SPA edits profiles; the launcher persists them. */
export function useProfileMutations() {
  const queryClient = useQueryClient()
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["launcher", "profiles"] })
  const save = useMutation({
    mutationFn: ({ name, baseUrl }: { name: string; baseUrl: string }) =>
      launcherApi.saveProfile(name, baseUrl),
    onSuccess: invalidate,
  })
  const activate = useMutation({
    mutationFn: (name: string | null) => launcherApi.setProfileActive(name),
    onSuccess: invalidate,
  })
  const remove = useMutation({
    mutationFn: (name: string) => launcherApi.deleteProfile(name),
    onSuccess: invalidate,
  })
  return { save, activate, remove }
}
