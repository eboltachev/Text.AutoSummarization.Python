"""Minimal exceptions module to satisfy third-party imports.

This shim mimics the subset of the public API exposed by ``requests``
that external dependencies (for example ``huggingface_hub``) rely on.
The goal is to provide the expected exception hierarchy without pulling
in the full ``requests`` dependency while still interoperating with the
rest of the lightweight HTTP wrapper bundled with the project.
"""

from __future__ import annotations

from json import JSONDecodeError as _JSONDecodeError


class RequestException(Exception):
    """Base exception used by the real ``requests`` package."""


class HTTPError(RequestException):
    """HTTP layer error raised for non-success responses."""

    def __init__(self, *args, response=None, request=None):
        super().__init__(*args)
        self.response = response
        self.request = request


class ConnectionError(RequestException):
    """Network level communication failure."""


class JSONDecodeError(RequestException, _JSONDecodeError):
    """JSON parsing error wrapper to match ``requests`` semantics."""

    def __init__(self, msg, doc, pos):
        RequestException.__init__(self, msg)
        _JSONDecodeError.__init__(self, msg, doc, pos)


__all__ = [
    "RequestException",
    "HTTPError",
    "ConnectionError",
    "JSONDecodeError",
]
