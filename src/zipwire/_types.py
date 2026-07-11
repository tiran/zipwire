"""Reader protocols for sync and async IO."""

from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


@typing.runtime_checkable
class SyncReader(typing.Protocol):
    """Protocol for synchronous HTTP range-request readers."""

    def read_range(self, offset: int, length: int) -> bytes:
        """Read *length* bytes starting at *offset*."""
        ...

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        """Stream *length* bytes starting at *offset* as chunks."""
        ...

    def get_content_length(self) -> int:
        """Return the total size of the remote resource in bytes."""
        ...

    def close(self) -> None:
        """Release any held resources."""
        ...


@typing.runtime_checkable
class AsyncReader(typing.Protocol):
    """Protocol for asynchronous HTTP range-request readers."""

    async def read_range(self, offset: int, length: int) -> bytes:
        """Read *length* bytes starting at *offset*."""
        ...

    def stream_range(self, offset: int, length: int) -> AsyncIterator[bytes]:
        """Stream *length* bytes starting at *offset* as chunks."""
        ...

    async def get_content_length(self) -> int:
        """Return the total size of the remote resource in bytes."""
        ...

    async def close(self) -> None:
        """Release any held resources."""
        ...


@typing.runtime_checkable
class Writable(typing.Protocol):
    """Protocol for writable file-like objects (io.BytesIO, io.BufferedWriter, etc.)."""

    def write(self, data: bytes, /) -> object: ...
