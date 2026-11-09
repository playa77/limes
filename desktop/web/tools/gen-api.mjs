// desktop/web/tools/gen-api.mjs
// Regenerates the committed API contract emitted from the LIMES API, then the
// typed TS schema: `tools/export_openapi.py` (venv python; no server run) is
// the single export seam, openapi-typescript consumes plain positional input.
// Local dev: `pnpm gen:api`. CI re-checks freshness in pytest (no node there).
import { execFileSync } from "node:child_process"
import { existsSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const repoRoot = path.resolve(webDir, "..", "..")

function pythonExecutable() {
  const candidates = []
  if (process.env.VIRTUAL_ENV) candidates.push(path.join(process.env.VIRTUAL_ENV, "bin", "python"))
  const repoVenv = path.join(repoRoot, "venv", "bin", "python")
  if (existsSync(repoVenv)) candidates.push(repoVenv)
  candidates.push("python3")
  return candidates
}

const exporter = path.join(repoRoot, "tools", "export_openapi.py")
let lastError = null
for (const python of pythonExecutable()) {
  try {
    execFileSync(python, [exporter], { cwd: repoRoot, stdio: "inherit" })
    process.exit(0)
  } catch (error) {
    lastError = error
  }
}
console.error(
  "gen:api failed: no python environment could run tools/export_openapi.py " +
    "(need the canonical venv with `limes` installed). " +
    String(lastError?.message ?? lastError ?? ""),
)
process.exit(1)
