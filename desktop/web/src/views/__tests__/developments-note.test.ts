// src/views/__tests__/developments-note.test.ts
// DC-16 (and BE-44) acceptance text — the retired Qt panel appended the
// no-causality disclaimer to its detail view; DC-17 carries the rule into
// the web client verbatim. Pinned against drift because the wording is the
// evidence-bearing statement itself.

import { describe, expect, it } from "vitest"

import { NO_CAUSALITY_NOTE } from "@/views/developments-view"

describe("developments no-causality rule", () => {
  it("carries the retired panel's disclaimer verbatim", () => {
    expect(NO_CAUSALITY_NOTE.trim()).toBe("Chronology implies neither causation nor misconduct.")
    expect(NO_CAUSALITY_NOTE.startsWith("\n")).toBe(true)
  })
})
