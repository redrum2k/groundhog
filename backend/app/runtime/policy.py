"""Current capture policy; invoice early-capture and rejected-claim fees are retired."""

from app.runtime.catalog_policy import capture_allowed

__all__ = ["capture_allowed"]
