// src/api/errors.ts
// Ported from the retired `limes_desktop/api/errors.py`: connection-level
// failures are `ApiUnreachable`, non-2xx responses are `ApiError` with the
// API's error body preserved verbatim (FR-DC-032: the wording is diagnostic
// signal — no rephrasing, no prefix).

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }

  /** True when the API told us no valid bearer token was supplied. */
  get isUnauthorized(): boolean {
    return this.status === 401
  }
}

export class ApiUnreachable extends Error {
  constructor(message = "API transport unavailable") {
    super(message)
    this.name = "ApiUnreachable"
  }
}
