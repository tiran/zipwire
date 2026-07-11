"""Synchronous requests-based reader."""

from __future__ import annotations

import typing

try:
    import requests
except ImportError as exc:
    raise ImportError(
        "RequestsReader requires requests. Install it with: pip install zipwire[requests]"
    ) from exc

from zipwire._constants import STREAM_CHUNK_SIZE
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


class RequestsReader:
    """SyncReader implementation using requests.Session."""

    def __init__(self, url: str, *, session: requests.Session | None = None) -> None:
        self._url = url
        self._owns_session = session is None
        self._session = session or requests.Session()

    def get_content_length(self) -> int:
        resp = self._session.head(self._url)
        resp.raise_for_status()
        if resp.headers.get("accept-ranges", "").lower() != "bytes":
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return int(resp.headers["content-length"])

    def read_range(self, offset: int, length: int) -> bytes:
        end = offset + length - 1
        resp = self._session.get(self._url, headers={"Range": f"bytes={offset}-{end}"})
        resp.raise_for_status()
        return resp.content

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        end = offset + length - 1
        resp = self._session.get(
            self._url, headers={"Range": f"bytes={offset}-{end}"}, stream=True
        )
        resp.raise_for_status()
        yield from resp.iter_content(chunk_size=STREAM_CHUNK_SIZE)

    def close(self) -> None:
        if self._owns_session:
            self._session.close()
