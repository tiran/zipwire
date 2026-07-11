"""Decompression and CRC verification for ZIP entries."""

from __future__ import annotations

import typing
import zlib
from enum import Enum

from zipwire._constants import CompressionMethod
from zipwire._errors import CRCMismatch, UnsupportedCompression

if typing.TYPE_CHECKING:
    from zipwire._types import Writable


class _DecompressMode(Enum):
    """Internal mode tags for StreamingDecompressor."""

    STORED = "stored"
    DEFLATED = "deflated"
    INCREMENTAL = "incremental"


def decompress(
    data: bytes,
    method: int,
    expected_size: int,
    expected_crc: int,
) -> bytes:
    """Decompress data and verify CRC-32.

    Args:
        data: The raw (possibly compressed) file data.
        method: ZIP compression method (0=stored, 8=deflated, 12=bzip2, 14=lzma, 93=zstandard).
        expected_size: Expected uncompressed size.
        expected_crc: Expected CRC-32 of the uncompressed data.

    Returns:
        The decompressed bytes.

    Raises:
        UnsupportedCompression: If the compression method is not supported.
        CRCMismatch: If the CRC-32 check fails.
    """
    match method:
        case CompressionMethod.STORED:
            result = data
        case CompressionMethod.DEFLATED:
            # -15 = raw deflate (no zlib/gzip header)
            result = zlib.decompress(data, -15)
        case CompressionMethod.BZIP2:
            try:
                import bz2
            except ImportError:
                raise UnsupportedCompression(method) from None

            result = bz2.decompress(data)
        case CompressionMethod.LZMA:
            try:
                import lzma
            except ImportError:
                raise UnsupportedCompression(method) from None

            result = lzma.decompress(data)
        case CompressionMethod.ZSTANDARD:
            try:
                import zstandard  # ty: ignore[unresolved-import]
            except ImportError:
                raise UnsupportedCompression(method) from None

            result = zstandard.decompress(data)
        case _:
            raise UnsupportedCompression(method)

    actual_crc = zlib.crc32(result) & 0xFFFFFFFF
    if actual_crc != expected_crc:
        raise CRCMismatch(expected_crc, actual_crc)

    return result


class StreamingDecompressor:
    """Feed compressed chunks via :meth:`feed`, then call :meth:`finish` to verify CRC-32."""

    def __init__(self, method: int, expected_crc: int, dest: Writable) -> None:
        self._expected_crc = expected_crc
        self._dest = dest
        self._crc: int = 0
        self._dobj: typing.Any = None

        match method:
            case CompressionMethod.STORED:
                self._mode = _DecompressMode.STORED
            case CompressionMethod.DEFLATED:
                self._mode = _DecompressMode.DEFLATED
                self._dobj = zlib.decompressobj(-15)
            case CompressionMethod.BZIP2:
                try:
                    import bz2
                except ImportError:
                    raise UnsupportedCompression(method) from None

                self._mode = _DecompressMode.INCREMENTAL
                self._dobj = bz2.BZ2Decompressor()
            case CompressionMethod.LZMA:
                try:
                    import lzma
                except ImportError:
                    raise UnsupportedCompression(method) from None

                self._mode = _DecompressMode.INCREMENTAL
                self._dobj = lzma.LZMADecompressor()
            case CompressionMethod.ZSTANDARD:
                try:
                    import zstandard  # ty: ignore[unresolved-import]
                except ImportError:
                    raise UnsupportedCompression(method) from None

                self._mode = _DecompressMode.INCREMENTAL
                self._dobj = zstandard.ZstdDecompressor().decompressobj()
            case _:
                raise UnsupportedCompression(method)

    def feed(self, data: bytes) -> None:
        """Decompress *data*, write output to dest, update CRC."""
        if self._mode is _DecompressMode.STORED:
            self._crc = zlib.crc32(data, self._crc)
            self._dest.write(data)
        else:
            # deflate, bz2, lzma, zstandard - all expose .decompress()
            chunk = self._dobj.decompress(data)
            if chunk:
                self._crc = zlib.crc32(chunk, self._crc)
                self._dest.write(chunk)

    def finish(self) -> None:
        """Flush remaining data (deflate only) and verify CRC-32."""
        if self._mode is _DecompressMode.DEFLATED:
            chunk = self._dobj.flush()
            if chunk:
                self._crc = zlib.crc32(chunk, self._crc)
                self._dest.write(chunk)

        actual_crc = self._crc & 0xFFFFFFFF
        if actual_crc != self._expected_crc:
            raise CRCMismatch(self._expected_crc, actual_crc)
