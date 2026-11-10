import { expect, it } from "vitest"
import { diagnosisFromApi, nlqOutcomeFromApi, operationJobFromApi } from "../types"

it("accepts queued Job.output before the worker has produced output", () => {
  expect(operationJobFromApi({
    job_id: "fixture-job", request: { request_id: "fixture-job", command: "backup" },
    status: "queued", created_at: "2026-11-09T12:00:00Z", updated_at: "2026-11-09T12:00:00Z", output: "",
  }).output).toBe("")
})
it("preserves an empty generated query and its validation errors", () => {
  const outcome = nlqOutcomeFromApi({ question: "Find a connection", cypher: "", validation_errors: ["Empty Cypher"] })
  expect(outcome.cypher).toBe("")
  expect(outcome.validation_errors).toEqual(["Empty Cypher"])
})
it("accepts an empty-result diagnosis without a failing clause and rejects non-text", () => {
  const diagnosis = { failing_clause: "", clause_index: -1, relation_counts: {}, note: "No matching entities" }
  expect(diagnosisFromApi(diagnosis).note).toBe("No matching entities")
  expect(() => diagnosisFromApi({ ...diagnosis, note: 42 })).toThrow("expects a string for note")
})
