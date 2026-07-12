"""Synchronous and asynchronous httpx2-based readers."""

from __future__ import annotations

import typing

try:
    import httpx2
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "httpx2 readers require httpx2. Install it with: pip install zipwire[httpx2]"
    ) from exc

try:
    import h2  # noqa: F401

    _h2_available = True
except ImportError:  # pragma: no cover
    _h2_available = False

from zipwire._constants import STREAM_CHUNK_SIZE, range_header
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from zipwire._types import Headers


class Httpx2SyncReader:
    """SyncReader implementation using httpx2.Client."""

    def __init__(
        self,
        url: str,
        *,
        client: httpx2.Client | None = None,
        http2: bool | None = None,
    ) -> None:
        self._url = url
        self._owns_client = client is None
        if http2 is None:
            http2 = _h2_available
        self._client = client or httpx2.Client(http2=http2)

    def head(self) -> Headers:
        resp = self._client.head(self._url)
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
        resp = self._client.get(self._url, headers={"Range": range_header(offset, length)})
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.content, resp.headers

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        with self._client.stream(
            "GET", self._url, headers={"Range": range_header(offset, length)}
        ) as resp:
            resp.raise_for_status()
            yield from resp.iter_bytes(chunk_size=STREAM_CHUNK_SIZE)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class Httpx2AsyncReader:
    """AsyncReader implementation using httpx2.AsyncClient."""

    def __init__(
        self,
        url: str,
        *,
        client: httpx2.AsyncClient | None = None,
        http2: bool | None = None,
    ) -> None:
        self._url = url
        self._owns_client = client is None
        if http2 is None:
            http2 = _h2_available
        self._client = client or httpx2.AsyncClient(http2=http2)

    async def head(self) -> Headers:
        resp = await self._client.head(self._url)
        resp.raise_for_status()
        if resp.headers.get("accept-ranges", "").lower() != "bytes":
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.headers

    async def read_range(
        self,
        offset: int,
        length: int,
    ) -> tuple[bytes, Headers]:
        resp = await self._client.get(self._url, headers={"Range": range_header(offset, length)})
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.content, resp.headers

    async def stream_range(self, offset: int, length: int) -> AsyncIterator[bytes]:
        async with self._client.stream(
            "GET", self._url, headers={"Range": range_header(offset, length)}
        ) as resp:
            resp.raise_for_status()
            async for chunk in resp.aiter_bytes(chunk_size=STREAM_CHUNK_SIZE):
                yield chunk

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
