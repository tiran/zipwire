"""Synchronous urllib3-based reader."""

from __future__ import annotations

import typing

import urllib3

from zipwire._constants import STREAM_CHUNK_SIZE
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import Iterator


class Urllib3Reader:
    """SyncReader implementation using urllib3.PoolManager."""

    def __init__(self, url: str, *, pool: urllib3.PoolManager | None = None) -> None:
        self._url = url
        self._owns_pool = pool is None
        self._pool = pool or urllib3.PoolManager()

    def get_content_length(self) -> int:
        resp = self._pool.request("HEAD", self._url)
        if resp.status >= 400:
            raise OSError(f"HEAD request failed with status {resp.status}")
        if resp.headers.get("accept-ranges", "").lower() != "bytes":
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return int(resp.headers["content-length"])

    def read_range(self, offset: int, length: int) -> bytes:
        end = offset + length - 1
        resp = self._pool.request("GET", self._url, headers={"Range": f"bytes={offset}-{end}"})
        if resp.status >= 400:
            raise OSError(f"Range request failed with status {resp.status}")
        return bytes(resp.data)

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        end = offset + length - 1
        resp = self._pool.request(
            "GET",
            self._url,
            headers={"Range": f"bytes={offset}-{end}"},
            preload_content=False,
        )
        if resp.status >= 400:
            resp.release_conn()
            raise OSError(f"Range request failed with status {resp.status}")
        try:
            yield from resp.stream(STREAM_CHUNK_SIZE)
        finally:
            resp.release_conn()

    def close(self) -> None:
        if self._owns_pool:
            self._pool.clear()
