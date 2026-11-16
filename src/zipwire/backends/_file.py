"""Local-file readers that satisfy the SyncReader / AsyncReader protocols.

``FileReader`` and ``AsyncFileReader`` back the same
:class:`~zipwire.SyncRemoteZip` / :class:`~zipwire.AsyncRemoteZip` API with
local file IO, so an archive on disk opens exactly like a remote one.  They
are useful for testing, for treating ``file://`` URIs uniformly with HTTP
URLs, and for reading a wheel or ZIP that already lives on the local
filesystem without a running HTTP server.

Unlike the HTTP backends there is no network round-trip: :meth:`head`
synthesises headers from ``os.fstat`` on the open handle (the size is
cached, assuming the file does not change), and range reads seek into a
lazily-opened file handle.

Regular files do not support true non-blocking IO (``epoll``/``select`` and
``O_NONBLOCK`` do not apply to them), so ``AsyncFileReader`` offloads every
blocking call to a worker thread via :func:`anyio.to_thread.run_sync` -- the
same strategy libraries such as ``aiofiles`` use internally, without the
extra dependency.  Because anyio drives the offloading, the reader works on
asyncio and trio alike, and cancellation is safe: an in-flight blocking
call always runs to completion and its worker thread is never abandoned,
so the file handle is never closed or reused underneath a thread that is
still using it.
"""

from __future__ import annotations

import os
import typing
from urllib.parse import urlparse
from urllib.request import url2pathname

import anyio

from zipwire._constants import STREAM_CHUNK_SIZE

if typing.TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Generator

    from zipwire._types import Headers


def _path_from_file_uri(uri: str) -> str:
    """Convert a ``file://`` URI to a local filesystem path.

    Accepts an empty or ``localhost`` host and percent-decodes the path
    via :func:`urllib.request.url2pathname`.

    Raises:
        ValueError: If *uri* is not a ``file://`` URI or names a remote host.
    """
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        raise ValueError(f"Not a file:// URI: {uri!r}")
    if parsed.netloc not in ("", "localhost"):
        raise ValueError(f"Non-local file URI host {parsed.netloc!r} in {uri!r}")
    return url2pathname(parsed.path)


def _stat_headers(size: int) -> dict[str, str]:
    """Synthesise HTTP-style headers describing a local file of *size* bytes."""
    return {"content-length": str(size), "accept-ranges": "bytes"}


class FileReader:
    """SyncReader implementation backed by a local file.

    Opens the file lazily on the first read and keeps a single handle
    open until :meth:`close` (or context-manager exit).  A missing path
    surfaces as :exc:`FileNotFoundError`, mirroring how an HTTP 404
    surfaces as :exc:`OSError` in the network backends.
    """

    def __init__(self, path: str | os.PathLike[str], *, url: str | None = None) -> None:
        self._path = os.fspath(path)
        self._url = url if url is not None else self._path
        self._handle: typing.BinaryIO | None = None
        self._size: int | None = None

    @classmethod
    def from_uri(cls, uri: str) -> FileReader:
        """Create a :class:`FileReader` from a ``file://`` URI."""
        return cls(_path_from_file_uri(uri), url=uri)

    @property
    def url(self) -> str:
        """The original path or ``file://`` URI for this reader."""
        return self._url

    def _open(self) -> typing.BinaryIO:
        if self._handle is None:
            self._handle = open(self._path, "rb")  # noqa: SIM115
        return self._handle

    def _file_size(self) -> int:
        # Cached from fstat on the open handle.  We assume the file does
        # not change for the lifetime of the reader.
        if self._size is None:
            self._size = os.fstat(self._open().fileno()).st_size
        return self._size

    def head(self) -> Headers:
        return _stat_headers(self._file_size())  # type: ignore[return-value]

    def read_range(self, offset: int, length: int) -> tuple[bytes, Headers]:
        fh = self._open()
        fh.seek(offset)
        data = fh.read(length)
        return data, _stat_headers(self._file_size())  # type: ignore[return-value]

    def stream_range(self, offset: int, length: int) -> Generator[bytes, None, None]:
        fh = self._open()
        fh.seek(offset)
        remaining = length
        while remaining > 0:
            chunk = fh.read(min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None
        self._size = None

    def __enter__(self) -> FileReader:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class AsyncFileReader:
    """AsyncReader implementation backed by a local file.

    Regular files cannot be read without blocking, so every blocking
    call is offloaded to a worker thread with
    :func:`anyio.to_thread.run_sync`, keeping the event loop responsive.
    The reader is loop-agnostic and works under asyncio and trio.  A
    missing path surfaces as :exc:`FileNotFoundError`, mirroring how an
    HTTP 404 surfaces as :exc:`OSError` in the network backends.

    Cancellation uses anyio's default ``abandon_on_cancel=False``
    semantics: a read that is cancelled while its worker thread is
    running waits for the blocking call to finish, and the cancellation
    is then absorbed.  A cancelled read never abandons a worker thread
    that still holds the file handle.
    """

    def __init__(self, path: str | os.PathLike[str], *, url: str | None = None) -> None:
        self._path = os.fspath(path)
        self._url = url if url is not None else self._path
        self._handle: typing.BinaryIO | None = None
        self._size: int | None = None

    @classmethod
    def from_uri(cls, uri: str) -> AsyncFileReader:
        """Create an :class:`AsyncFileReader` from a ``file://`` URI."""
        return cls(_path_from_file_uri(uri), url=uri)

    @property
    def url(self) -> str:
        """The original path or ``file://`` URI for this reader."""
        return self._url

    def _open(self) -> typing.BinaryIO:
        if self._handle is None:
            self._handle = open(self._path, "rb")  # noqa: SIM115
        return self._handle

    def _file_size(self) -> int:
        # Cached from fstat on the open handle.  We assume the file does
        # not change for the lifetime of the reader.
        if self._size is None:
            self._size = os.fstat(self._open().fileno()).st_size
        return self._size

    async def head(self) -> Headers:
        size = await anyio.to_thread.run_sync(self._file_size)
        return _stat_headers(size)  # type: ignore[return-value]

    async def read_range(self, offset: int, length: int) -> tuple[bytes, Headers]:
        def _read() -> tuple[bytes, int]:
            fh = self._open()
            fh.seek(offset)
            return fh.read(length), self._file_size()

        data, size = await anyio.to_thread.run_sync(_read)
        return data, _stat_headers(size)  # type: ignore[return-value]

    async def stream_range(self, offset: int, length: int) -> AsyncGenerator[bytes, None]:
        def _open_seek() -> typing.BinaryIO:
            fh = self._open()
            fh.seek(offset)
            return fh

        fh = await anyio.to_thread.run_sync(_open_seek)
        remaining = length
        while remaining > 0:
            chunk = await anyio.to_thread.run_sync(fh.read, min(STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk

    async def close(self) -> None:
        # Detach the handle before closing it: if the awaiting task is
        # cancelled, the blocking close() still runs to completion in the
        # worker thread and a repeated close() becomes a no-op.
        handle, self._handle = self._handle, None
        if handle is not None:
            await anyio.to_thread.run_sync(handle.close)
        self._size = None

    async def __aenter__(self) -> AsyncFileReader:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
