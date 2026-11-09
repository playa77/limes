import js from "@eslint/js"
import globals from "globals"
import reactHooks from "eslint-plugin-react-hooks"
import reactRefresh from "eslint-plugin-react-refresh"
import tseslint from "typescript-eslint"
import { globalIgnores } from "eslint/config"

// Lint posture for the web client: TypeScript strictness plus the classical
// hook pair on our own views/state. The react-hooks v7 compiler-preview rules
// (refs, set-state-in-effect, static-components, use-memo…) reject deliberate
// external-system synchronization effects and the vendored ReUI sources; they
// are not adopted until a dedicated pass.
export default tseslint.config([
  globalIgnores(["dist", "src/api/schema.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    // Vendored upstream sources (shadcn/Radix base + ReUI blocks)
    // legitimately export variants/defaults from component files, carry
    // effect patterns tuned by their authors, and keep their own inline
    // eslint-disable history and wider conventions.
    files: ["src/components/ui/**", "src/components/reui/**"],
    linterOptions: {
      reportUnusedDisableDirectives: "off",
    },
    rules: {
      "react-refresh/only-export-components": "off",
      "react-hooks/exhaustive-deps": "off",
      // ANSI control-character regexes are the highlighter's data, and
      // upstream names deliberately-unused parameters with a leading
      // underscore.
      "no-control-regex": "off",
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
])
