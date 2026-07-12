"""Test fixtures: generate ZIP files and provide mock readers."""

from __future__ import annotations

import io
import typing
import zipfile

import pytest

if typing.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator


def make_zip(files: dict[str, bytes], *, compression: int = zipfile.ZIP_STORED) -> bytes:
    """Create an in-memory ZIP archive.

    Args:
        files: Mapping of filename to content.
        compression: ZIP compression method (ZIP_STORED or ZIP_DEFLATED).

    Returns:
        Raw bytes of the ZIP file.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compression) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class MockSyncReader:
    """A SyncReader backed by in-memory bytes (simulates a remote ZIP)."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False
        self.read_count = 0

    def head(self) -> dict[str, str]:
        return {
            "content-length": str(len(self.data)),
            "accept-ranges": "bytes",
        }

    def read_range(
        self,
        offset: int,
        length: int,
    ) -> tuple[bytes, dict[str, str]]:
        self.read_count += 1
        total = len(self.data)
        chunk = self.data[offset : offset + length]
        end = offset + len(chunk) - 1
        headers = {"content-range": f"bytes {offset}-{end}/{total}"}
        return chunk, headers

    def stream_range(self, offset: int, length: int) -> Iterator[bytes]:
        data = self.data[offset : offset + length]
        chunk_size = 1024
        for pos in range(0, len(data), chunk_size):
            self.read_count += 1
            yield data[pos : pos + chunk_size]

    def close(self) -> None:
        self.closed = True


class MockAsyncReader:
    """An AsyncReader backed by in-memory bytes."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False
        self.read_count = 0

    async def head(self) -> dict[str, str]:
        return {
            "content-length": str(len(self.data)),
            "accept-ranges": "bytes",
        }

    async def read_range(
        self,
        offset: int,
        length: int,
    ) -> tuple[bytes, dict[str, str]]:
        self.read_count += 1
        total = len(self.data)
        chunk = self.data[offset : offset + length]
        end = offset + len(chunk) - 1
        headers = {"content-range": f"bytes {offset}-{end}/{total}"}
        return chunk, headers

    async def stream_range(self, offset: int, length: int) -> AsyncIterator[bytes]:
        data = self.data[offset : offset + length]
        chunk_size = 1024
        for pos in range(0, len(data), chunk_size):
            self.read_count += 1
            yield data[pos : pos + chunk_size]

    async def close(self) -> None:
        self.closed = True


# --- Fixtures ---


@pytest.fixture
def stored_zip() -> bytes:
    """ZIP with STORED files."""
    return make_zip(
        {
            "hello.txt": b"Hello, World!",
            "data/numbers.bin": b"\x01\x02\x03\x04\x05",
        }
    )


@pytest.fixture
def deflated_zip() -> bytes:
    """ZIP with DEFLATED files."""
    return make_zip(
        {
            "hello.txt": b"Hello, World!",
            "data/numbers.bin": b"\x01\x02\x03\x04\x05",
            "repeated.txt": b"AAAA" * 1000,
        },
        compression=zipfile.ZIP_DEFLATED,
    )


@pytest.fixture
def mixed_zip() -> bytes:
    """ZIP with both STORED and DEFLATED files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            zipfile.ZipInfo("stored.txt"),
            b"stored content",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr(
            zipfile.ZipInfo("deflated.txt"),
            b"deflated " * 100,
            compress_type=zipfile.ZIP_DEFLATED,
        )
    return buf.getvalue()


@pytest.fixture
def unicode_zip() -> bytes:
    """ZIP with unicode filenames."""
    return make_zip(
        {
            "\u00e9\u00e0\u00fc.txt": b"unicode content",
            "\u4f60\u597d/world.txt": b"hello",
        }
    )


@pytest.fixture
def directory_zip() -> bytes:
    """ZIP with explicit directory entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.mkdir("emptydir/")
        zf.writestr("emptydir/file.txt", b"inside dir")
    return buf.getvalue()


@pytest.fixture
def empty_zip() -> bytes:
    """ZIP with no files."""
    return make_zip({})


@pytest.fixture
def comment_zip() -> bytes:
    """ZIP with an archive comment."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("file.txt", b"content")
        zf.comment = b"This is a ZIP comment"
    return buf.getvalue()


@pytest.fixture
def large_file_zip() -> bytes:
    """ZIP with a STORED file exceeding PREFETCH_THRESHOLD (50 KiB)."""
    content = bytes(range(256)) * 208  # 53248 bytes = 52 KiB
    return make_zip({"large.bin": content})


@pytest.fixture
def zstandard_zip() -> bytes:
    """ZIP with ZSTANDARD-compressed files (requires Python 3.14+ and zstandard)."""
    pytest.importorskip("zstandard")
    return make_zip(
        {
            "hello.txt": b"Hello, World!",
            "repeated.txt": b"AAAA" * 1000,
        },
        compression=zipfile.ZIP_ZSTANDARD,
    )
