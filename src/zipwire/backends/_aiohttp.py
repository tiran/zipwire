"""Asynchronous aiohttp-based reader."""

from __future__ import annotations

import typing

try:
    import aiohttp
except ImportError as exc:
    raise ImportError(
        "AiohttpReader requires aiohttp. Install it with: pip install zipwire[aiohttp]"
    ) from exc

from zipwire._constants import STREAM_CHUNK_SIZE
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator


class AiohttpReader:
    """AsyncReader implementation using aiohttp.ClientSession."""

    def __init__(self, url: str, *, session: aiohttp.ClientSession | None = None) -> None:
        self._url = url
        self._owns_session = session is None
        self._session = session or aiohttp.ClientSession()

    async def get_content_length(self) -> int:
        async with self._session.head(self._url) as resp:
            resp.raise_for_status()
            if resp.headers.get("accept-ranges", "").lower() != "bytes":
                raise RangeRequestUnsupported(
                    f"Server does not support range requests for {self._url}"
                )
            return int(resp.headers["content-length"])

    async def read_range(self, offset: int, length: int) -> bytes:
        end = offset + length - 1
        headers = {"Range": f"bytes={offset}-{end}"}
        async with self._session.get(self._url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.read()

    async def stream_range(self, offset: int, length: int) -> AsyncIterator[bytes]:
        end = offset + length - 1
        headers = {"Range": f"bytes={offset}-{end}"}
        async with self._session.get(self._url, headers=headers) as resp:
            resp.raise_for_status()
            async for chunk in resp.content.iter_chunked(STREAM_CHUNK_SIZE):
                yield chunk

    async def close(self) -> None:
        if self._owns_session:
            await self._session.close()
