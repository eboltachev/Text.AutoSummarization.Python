"""Minimal adapters module mimicking the public ``requests`` API.

The bundled implementation does not provide a full HTTP transport layer,
but several third-party libraries import ``requests.adapters.HTTPAdapter``
purely for configuration.  The lightweight class below records the
requested parameters so callers can instantiate and mount adapters without
raising import errors.
"""

from __future__ import annotations

from typing import Any, Optional


class BaseAdapter:
    def close(self) -> None:  # pragma: no cover - no resources to release
        """Mirror the close hook from ``requests.adapters.BaseAdapter``."""


class HTTPAdapter(BaseAdapter):
    """Placeholder adapter capturing retry configuration."""

    def __init__(self, *args: Any, max_retries: Optional[Any] = None, **kwargs: Any) -> None:
        super().__init__()
        self.max_retries = max_retries
        self.args = args
        self.kwargs = kwargs


DEFAULT_POOLBLOCK = False
DEFAULT_POOLSIZE = 10


__all__ = ["HTTPAdapter", "BaseAdapter", "DEFAULT_POOLBLOCK", "DEFAULT_POOLSIZE"]

