"""Synchronous httpx2-based reader."""

from __future__ import annotations

import typing

try:
    import httpx2
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Httpx2SyncReader requires httpx2. Install it with: pip install zipwire[httpx2]"
    ) from exc

from zipwire._constants import STREAM_CHUNK_SIZE, Whence
from zipwire._errors import RangeRequestUnsupported

if typing.TYPE_CHECKING:
    from collections.abc import Iterator

    from zipwire._types import Headers


class Httpx2SyncReader:
    """SyncReader implementation using httpx2.Client."""

    def __init__(self, url: str, *, client: httpx2.Client | None = None) -> None:
        self._url = url
        self._owns_client = client is None
        self._client = client or httpx2.Client()

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
        whence: int = Whence.OFFSET,
    ) -> tuple[bytes, Headers]:
        match whence:
            case Whence.OFFSET:
                end = offset + length - 1
                range_header = f"bytes={offset}-{end}"
            case Whence.END:
                range_header = f"bytes=-{length}"
            case _:  # pragma: no cover
                raise ValueError(f"unsupported whence value: {whence!r}")
        resp = self._client.get(self._url, headers={"Range": range_header})
        resp.raise_for_status()
        if resp.status_code != 206:
            raise RangeRequestUnsupported(
                f"Server does not support range requests for {self._url}"
            )
        return resp.content, resp.headers

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
