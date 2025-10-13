from __future__ import annotations

import json as _json
import sys
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib import request as _request
from urllib.error import HTTPError, URLError

from . import exceptions as exceptions_module


@dataclass
class Response:
    """Lightweight response object that mirrors the real ``requests`` API."""

    status_code: int
    _content: bytes
    headers: Dict[str, Any]

    def json(self) -> Any:
        if not self._content:
            return None
        return _json.loads(self._content.decode("utf-8"))

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        return self._content.decode("utf-8", errors="replace")

    @property
    def content(self) -> bytes:
        return self._content

    def raise_for_status(self) -> None:
        if self.ok:
            return
        raise exceptions_module.HTTPError(
            f"HTTP {self.status_code}", response=self
        )


sys.modules[f"{__name__}.exceptions"] = exceptions_module
exceptions = exceptions_module


def _perform(method: str, url: str, headers: Optional[Dict[str, str]] = None, data: Optional[bytes] = None) -> Response:
    req = _request.Request(url=url, data=data, headers=headers or {}, method=method.upper())
    try:
        with _request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return Response(resp.getcode(), body, dict(resp.headers))
    except HTTPError as error:  # pragma: no cover - relies on remote server behaviour
        return Response(error.code, error.read() or b"", dict(error.headers or {}))
    except URLError as error:  # pragma: no cover - network errors
        raise error


def get(url: str, headers: Optional[Dict[str, str]] = None) -> Response:
    return _perform("GET", url, headers=headers)


def post(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json: Optional[Dict[str, Any]] = None,
    files: Optional[Dict[str, Any]] = None,
) -> Response:
    headers = headers.copy() if headers else {}
    data: Optional[bytes] = None
    if files:
        boundary = "----AutoSummarizationBoundary" + uuid.uuid4().hex
        parts: list[bytes] = []
        for name, value in files.items():
            filename, content, content_type = value
            if isinstance(content, str):
                content_bytes = content.encode("utf-8")
            else:
                content_bytes = content
            part = (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8")
                + content_bytes
                + b"\r\n"
            )
            parts.append(part)
        parts.append(f"--{boundary}--\r\n".encode("utf-8"))
        data = b"".join(parts)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif json is not None:
        data = _json.dumps(json).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    return _perform("POST", url, headers=headers, data=data)


def delete(url: str, headers: Optional[Dict[str, str]] = None, json: Optional[Dict[str, Any]] = None) -> Response:
    headers = headers.copy() if headers else {}
    data = None
    if json is not None:
        data = _json.dumps(json).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    return _perform("DELETE", url, headers=headers, data=data)


class Session:
    """Very small subset of ``requests.Session`` used by bundled clients."""

    def __init__(self) -> None:
        self.headers: Dict[str, str] = {}
        self._adapters: Dict[str, Any] = {}

    def mount(self, prefix: str, adapter: Any) -> None:  # pragma: no cover - trivial
        self._adapters[prefix] = adapter

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Response:
        merged_headers = {**self.headers, **(headers or {})}
        if method.upper() == "GET":
            return get(url, headers=merged_headers)
        if method.upper() == "DELETE":
            return delete(url, headers=merged_headers, json=json)
        return post(url, headers=merged_headers, json=json, files=files)

    def get(self, url: str, **kwargs: Any) -> Response:
        headers = kwargs.get("headers")
        return self.request("GET", url, headers=headers)

    def post(self, url: str, **kwargs: Any) -> Response:
        headers = kwargs.get("headers")
        json = kwargs.get("json")
        files = kwargs.get("files")
        return self.request("POST", url, headers=headers, json=json, files=files)

    def delete(self, url: str, **kwargs: Any) -> Response:
        headers = kwargs.get("headers")
        json = kwargs.get("json")
        return self.request("DELETE", url, headers=headers, json=json)

    def close(self) -> None:  # pragma: no cover - nothing to clean up
        self._adapters.clear()


def session() -> Session:
    return Session()


__all__ = [
    "Session",
    "session",
    "get",
    "post",
    "delete",
    "Response",
    "exceptions",
]
