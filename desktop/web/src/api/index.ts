// src/api/index.ts
// Singletons shared by every view. A single ApiClient per launcher origin
// (equivalent of the desktop's one httpx.Client per profile) and one
// LauncherApi for the local surfaces. Tests inject their own fetch.

import { ApiClient } from "@/api/client"
import { LauncherApi } from "@/api/launcher"

export const apiClient = new ApiClient()
export const launcherApi = new LauncherApi()
