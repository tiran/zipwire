"""Synchronous httpx2-based reader."""

from __future__ import annotations

import typing

try:
    import httpx2
except ImportError as exc:
    raise ImportError(
        "Httpx2SyncReader requires httpx2. Install it with: pip install zipwire[httpx2]"
    ) from exc

from zipwire._constants import STREAM_CHUNK_SIZE
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


class Httpx2SyncReader:
    """SyncReader implementation using httpx2.Client."""

    def __init__(self, url: str, *, client: httpx2.Client | None = None) -> None:
        self._url = url
        self._owns_client = client is None
        self._client = client or httpx2.Client()

    def get_content_length(self) -> int:
        resp = self._client.head(self._url)
        resp.raise_for_status()
        if resp.headers.get("accept-ranges", "").lower() != "bytes":
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return int(resp.headers["content-length"])

    def read_range(self, offset: int, length: int) -> bytes:
        end = offset + length - 1
        resp = self._client.get(self._url, headers={"Range": f"bytes={offset}-{end}"})
        resp.raise_for_status()
        return resp.content

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        end = offset + length - 1
        with self._client.stream(
            "GET", self._url, headers={"Range": f"bytes={offset}-{end}"}
        ) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes(chunk_size=STREAM_CHUNK_SIZE)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
