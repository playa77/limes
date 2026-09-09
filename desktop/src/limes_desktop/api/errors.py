# desktop/src/limes_desktop/api/errors.py | v0.1.0 | API failure exceptions (FR-DC-062)
class ApiUnreachable(Exception):
    """The LIMES API could not be reached (connection-level failure)."""


class ApiError(Exception):
    """The LIMES API returned a non-success response with a verbatim detail body."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"API error {status}: {detail}")
        self.status = status
        self.detail = detail
