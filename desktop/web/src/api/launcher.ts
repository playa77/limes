// src/api/launcher.ts
// The launcher's local-only surfaces (loopback FastAPI): connection profile
// CRUD over the XDG store and the session descriptor. Tokens never appear
// here — they live in launcher memory and travel only inside the proxy.

import { ApiError, ApiUnreachable } from "@/api/errors"

export interface SessionDescriptor {
  /** Which credential kind the proxy injects (never its value). */
  token_kind: "operator" | "api" | "none"
  profile: string | null
  base_url: string
}

export interface Profile {
  name: string
  base_url: string
}

export class LauncherApi {
  constructor(private readonly fetchImpl: typeof fetch = fetch) {}

  async session(): Promise<SessionDescriptor> {
    return (await this.send("GET", "/session")) as SessionDescriptor
  }

  async setToken(token: string): Promise<SessionDescriptor> {
    return (await this.send("POST", "/session/token", { token })) as SessionDescriptor
  }

  async profiles(): Promise<Profile[]> {
    const data = (await this.send("GET", "/profiles")) as Record<string, Profile>
    return Object.values(data ?? {})
  }

  async activeProfile(): Promise<{ active: string | null }> {
    return (await this.send("GET", "/profiles/active")) as { active: string | null }
  }

  async saveProfile(name: string, baseUrl: string): Promise<Profile> {
    return (await this.send("PUT", "/profiles", {
      name,
      base_url: baseUrl,
    })) as Profile
  }

  async setProfileActive(name: string | null): Promise<void> {
    await this.send("PUT", "/profiles/active", { active: name })
  }

  async deleteProfile(name: string): Promise<void> {
    await this.send("DELETE", `/profiles/${encodeURIComponent(name)}`)
  }

  private async send(method: string, path: string, body?: unknown): Promise<unknown> {
    let response: Response
    try {
      response = await this.fetchImpl(path, {
        method,
        headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    } catch {
      throw new ApiUnreachable(`launcher unavailable (${method} ${path})`)
    }
    if (!response.ok) {
      const text = await response.text()
      throw new ApiError(response.status, text.trim() === "" ? `${method} ${path} failed` : text)
    }
    if (response.status === 204) return null
    try {
      return (await response.json()) as unknown
    } catch {
      throw new ApiError(502, `launcher returned an invalid JSON response for ${path}`)
    }
  }
}

export function isLoopbackHostname(): boolean {
  return ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname)
}
