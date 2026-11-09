import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

// The launcher serves `dist/` at the root, so assets must be relocatable.
const root = import.meta.dirname ?? "."

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // The launcher serves the bundle at the launcher root; absolute asset URLs
  // keep deep links (`/ops/offices`…) from resolving `assets/` under the
  // route path, which a relative "./" base silently breaks on reload.
  base: "/",
  resolve: {
    alias: {
      "@": path.resolve(root, "./src"),
    },
  },
  server: {
    // `pnpm dev` proxies to a running launcher (default port 8747) so the
    // browser never talks to the API directly in development either.
    proxy: {
      "/api": { target: "http://127.0.0.1:8747", changeOrigin: false },
      "/profiles": { target: "http://127.0.0.1:8747", changeOrigin: false },
      "/session": { target: "http://127.0.0.1:8747", changeOrigin: false },
    },
  },
  build: {
    // Three visualization libraries are large; keep chunks navigable.
    chunkSizeWarningLimit: 1500,
  },
})
