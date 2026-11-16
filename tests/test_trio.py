"""Loop-agnostic smoke tests: the async API must run under trio, not just
asyncio.

pytest-asyncio's auto mode claims every ``async def`` test for asyncio, so
these tests are plain sync functions that drive anyio with the trio backend
directly.  Each one exercises one layer of the async stack: the anyio
checkpoints in ``adecompress()``, the thread-offloading ``AsyncFileReader``
(including cancellation of an in-flight read), and the httpx2 backend.
"""

from __future__ import annotations

import io
import threading
import typing
import zlib

import anyio

from tests.conftest import has_httpx2, make_zip, needs_httpx2, needs_trio
from tests.test_backends import range_handler
from tests.test_decompress import _deflate_compress
from zipwire import AsyncRemoteZip
from zipwire._constants import STREAM_CHUNK_SIZE
from zipwire._decompress import adecompress
from zipwire.backends import AsyncFileReader

if typing.TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import pytest
    from pytest_httpserver.httpserver import HTTPServer

if has_httpx2:
    from zipwire.backends import Httpx2AsyncReader


@needs_trio
def test_adecompress_checkpoints_under_trio() -> None:
    """adecompress() yields at its checkpoints so other tasks can run."""
    original = b"\0" * (2 * STREAM_CHUNK_SIZE)
    compressed = _deflate_compress(original)
    crc = zlib.crc32(original) & 0xFFFFFFFF

    async def main() -> None:
        observed = False

        async def observer() -> None:
            nonlocal observed
            observed = True

        async with anyio.create_task_group() as tg:
            tg.start_soon(observer)
            result = await adecompress(
                compressed, method=8, expected_size=len(original), expected_crc=crc
            )
            assert result == original
            # The observer only ran if adecompress() yielded inside the
            # task group body, i.e. its anyio checkpoints fired.
            assert observed

    anyio.run(main, backend="trio")


@needs_trio
def test_file_reader_under_trio(tmp_path: Path) -> None:
    """AsyncRemoteZip reads a local archive under trio."""
    data = make_zip(
        {
            "hello.txt": b"Hello from test!",
            "subdir/data.bin": b"\x00\x01\x02\x03",
        }
    )
    path = tmp_path / "test.zip"
    path.write_bytes(data)
    out = tmp_path / "out.bin"

    async def main() -> None:
        async with AsyncRemoteZip(AsyncFileReader(path)) as rz:
            assert rz.namelist() == ["hello.txt", "subdir/data.bin"]
            assert await rz.read("hello.txt") == b"Hello from test!"
            dest = io.BytesIO()
            await rz.read_into("subdir/data.bin", dest)
            assert dest.getvalue() == b"\x00\x01\x02\x03"
            # async writable objects work under trio as well
            async with await anyio.open_file(out, "wb") as fh:
                await rz.read_into("hello.txt", fh)

    anyio.run(main, backend="trio")
    assert out.read_bytes() == b"Hello from test!"


@needs_trio
def test_file_reader_cancel_never_abandons_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A read cancelled mid-flight is never abandoned.

    With anyio's default ``abandon_on_cancel=False`` semantics the
    blocking call runs to completion even when the surrounding scope is
    cancelled -- trio documents this as the call behaving "just like if
    we had called it synchronously".  The worker thread is therefore
    never abandoned mid-read, the file handle is not closed underneath
    it, and the reader closes cleanly afterwards.
    """
    path = tmp_path / "test.zip"
    path.write_bytes(make_zip({"hello.txt": b"Hello from test!"}))

    real_open: Callable[..., typing.IO[bytes]] = open
    read_started = threading.Event()
    release_read = threading.Event()
    completed: list[bytes] = []

    class SlowHandle:
        """File wrapper whose read() blocks until released."""

        def __init__(self, fh: typing.IO[bytes]) -> None:
            self._fh = fh

        def fileno(self) -> int:
            return self._fh.fileno()

        def seek(self, offset: int, whence: int = 0) -> int:
            return self._fh.seek(offset, whence)

        def read(self, size: int = -1) -> bytes:
            read_started.set()
            release_read.wait(timeout=10)
            data = self._fh.read(size)
            completed.append(data)
            return data

        def close(self) -> None:
            self._fh.close()

    def slow_open(path: str, mode: str = "rb") -> SlowHandle:
        assert mode == "rb"
        return SlowHandle(real_open(path, mode))

    # _file.py calls the open() builtin; a module-level "open" global
    # shadows it for that module only, so the patch stays scoped.
    monkeypatch.setattr("zipwire.backends._file.open", slow_open, raising=False)

    async def main() -> None:
        reader = AsyncFileReader(path)
        data = b""
        async with anyio.create_task_group() as tg:

            async def releaser() -> None:
                await anyio.sleep(0.05)
                release_read.set()

            tg.start_soon(releaser)
            with anyio.move_on_after(0.01):
                data, _ = await reader.read_range(0, 16)
            # The deadline fired while the worker thread was parked in
            # read(); the read still ran to completion instead of being
            # abandoned half-way through.  An abandoned thread would
            # still be parked on release_read at this point.
            assert read_started.is_set()
            assert completed
            assert data == path.read_bytes()[:16]
        await reader.close()
        assert reader._handle is None

    anyio.run(main, backend="trio")


@needs_httpx2
@needs_trio
def test_httpx2_backend_under_trio(httpserver: HTTPServer) -> None:
    """Smoke test: the httpx2 backend reads an archive under trio."""
    data = make_zip(
        {
            "hello.txt": b"Hello from test!",
            "subdir/data.bin": b"\x00\x01\x02\x03",
        }
    )
    httpserver.expect_request("/test.zip").respond_with_handler(range_handler(data))

    async def main() -> None:
        reader = Httpx2AsyncReader(httpserver.url_for("/test.zip"))
        async with AsyncRemoteZip(reader) as rz:
            assert rz.namelist() == ["hello.txt", "subdir/data.bin"]
            assert await rz.read("hello.txt") == b"Hello from test!"
            dest = io.BytesIO()
            await rz.read_into("hello.txt", dest)
            assert dest.getvalue() == b"Hello from test!"

    anyio.run(main, backend="trio")
