"""Reader protocols for sync and async IO."""

from __future__ import annotations

import typing

from zipwire._constants import Whence

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


@typing.runtime_checkable
class Headers(typing.Protocol):
    """HTTP response headers returned by :meth:`read_range`.

    Implementations must support case-insensitive lookup or use
    lower-case keys so that ``headers["content-range"]`` always works.

    All standard HTTP header mapping types satisfy this protocol,
    including ``urllib3.HTTPHeaderDict``, ``requests.structures.CaseInsensitiveDict``,
    ``httpx2.Headers``, ``aiohttp.CIMultiDictProxy``, and plain ``dict``
    with lower-case keys.
    """

    def __getitem__(self, key: str) -> str: ...

    def __contains__(self, key: object) -> bool: ...

    def get(self, key: str, default: str | None = None) -> str | None: ...


@typing.runtime_checkable
class SyncReader(typing.Protocol):
    """Protocol for synchronous HTTP range-request readers."""

    def read_range(
        self,
        offset: int,
        length: int,
        whence: int = Whence.OFFSET,
    ) -> tuple[bytes, Headers]:
        """Read *length* bytes and return ``(data, headers)``.

        *whence* controls how *offset* is interpreted:

        * ``Whence.OFFSET`` (default) -- *offset* is an absolute byte position.
          Sends ``Range: bytes=<offset>-<offset+length-1>``.
        * ``Whence.END`` -- read the last *length* bytes (*offset* is
          ignored).  Sends ``Range: bytes=-<length>``.

        Returns the response body and the HTTP response headers.  The
        ``Content-Range`` header can be used to determine the total
        resource size.
        """
        ...

    def head(self) -> Headers:
        """Send a HEAD request and return the response headers.

        Raises:
            RangeRequestUnsupported: If the server does not advertise
                ``Accept-Ranges: bytes``.
        """
        ...

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        """Stream *length* bytes starting at *offset* as chunks."""
        ...

    def close(self) -> None:
        """Release any held resources."""
        ...


@typing.runtime_checkable
class AsyncReader(typing.Protocol):
    """Protocol for asynchronous HTTP range-request readers."""

    async def read_range(
        self,
        offset: int,
        length: int,
        whence: int = Whence.OFFSET,
    ) -> tuple[bytes, Headers]:
        """Read *length* bytes and return ``(data, headers)``.

        *whence* controls how *offset* is interpreted:

        * ``Whence.OFFSET`` (default) -- *offset* is an absolute byte position.
          Sends ``Range: bytes=<offset>-<offset+length-1>``.
        * ``Whence.END`` -- read the last *length* bytes (*offset* is
          ignored).  Sends ``Range: bytes=-<length>``.

        Returns the response body and the HTTP response headers.  The
        ``Content-Range`` header can be used to determine the total
        resource size.
        """
        ...

    async def head(self) -> Headers:
        """Send a HEAD request and return the response headers.

        Raises:
            RangeRequestUnsupported: If the server does not advertise
                ``Accept-Ranges: bytes``.
        """
        ...

    def stream_range(self, offset: int, length: int) -> AsyncIterator[bytes]:
        """Stream *length* bytes starting at *offset* as chunks."""
        ...

    async def close(self) -> None:
        """Release any held resources."""
        ...


@typing.runtime_checkable
class Writable(typing.Protocol):
    """Protocol for writable file-like objects (io.BytesIO, io.BufferedWriter, etc.)."""

    def write(self, data: bytes, /) -> object: ...
