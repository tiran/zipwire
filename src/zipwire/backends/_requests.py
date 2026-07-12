"""Synchronous requests-based reader."""

from __future__ import annotations

import typing

try:
    import requests
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "RequestsReader requires requests. Install it with: pip install zipwire[requests]"
    ) from exc

from zipwire._constants import STREAM_CHUNK_SIZE, range_header
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from zipwire._types import Headers


class RequestsReader:
    """SyncReader implementation using requests.Session."""

    def __init__(self, url: str, *, session: requests.Session | None = None) -> None:
        self._url = url
        self._owns_session = session is None
        self._session = session or requests.Session()

    def head(self) -> Headers:
        resp = self._session.head(self._url)
        resp.raise_for_status()
        if resp.headers.get("accept-ranges", "").lower() != "bytes":
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.headers

    def read_range(
        self,
        offset: int,
        length: int,
    ) -> tuple[bytes, Headers]:
        resp = self._session.get(self._url, headers={"Range": range_header(offset, length)})
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.content, resp.headers

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        resp = self._session.get(
            self._url, headers={"Range": range_header(offset, length)}, stream=True
        )
        resp.raise_for_status()
        yield from resp.iter_content(chunk_size=STREAM_CHUNK_SIZE)

    def close(self) -> None:
        if self._owns_session:
            self._session.close()
