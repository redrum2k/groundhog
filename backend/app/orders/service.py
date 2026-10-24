"""Shared service errors/clock. Current lifecycle implementation: orders/catalog.py.

The v0.2 invoice executor was retired. Persisted invoices and exact command responses
are accessible through the trusted read-only historical API, never advanced on startup.
"""

from datetime import UTC, datetime


class DomainError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


def utc_now() -> datetime:
    return datetime.now(UTC)
