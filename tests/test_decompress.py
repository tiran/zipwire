"""Tests for decompression and CRC verification."""

from __future__ import annotations

import io
import zlib

import pytest

from zipwire._decompress import StreamingDecompressor, decompress
from zipwire._errors import CRCMismatch, UnsupportedCompression

# --- decompress() ---


def test_decompress_stored_simple() -> None:
    data = b"Hello, World!"
    crc = zlib.crc32(data) & 0xFFFFFFFF
    result = decompress(data, method=0, expected_size=len(data), expected_crc=crc)
    assert result == data


def test_decompress_stored_empty() -> None:
    data = b""
    crc = zlib.crc32(data) & 0xFFFFFFFF
    result = decompress(data, method=0, expected_size=0, expected_crc=crc)
    assert result == b""


def test_decompress_stored_binary() -> None:
    data = bytes(range(256))
    crc = zlib.crc32(data) & 0xFFFFFFFF
    result = decompress(data, method=0, expected_size=len(data), expected_crc=crc)
    assert result == data


def test_decompress_deflated_simple() -> None:
    original = b"Hello, World!"
    compressed = zlib.compress(original, level=6)[2:-4]  # strip zlib header/trailer
    crc = zlib.crc32(original) & 0xFFFFFFFF
    result = decompress(compressed, method=8, expected_size=len(original), expected_crc=crc)
    assert result == original


def test_decompress_deflated_repeated() -> None:
    original = b"AAAA" * 1000
    compressed = zlib.compress(original, level=6)[2:-4]
    crc = zlib.crc32(original) & 0xFFFFFFFF
    result = decompress(compressed, method=8, expected_size=len(original), expected_crc=crc)
    assert result == original


def test_decompress_crc_mismatch() -> None:
    data = b"Hello, World!"
    with pytest.raises(CRCMismatch):
        decompress(data, method=0, expected_size=len(data), expected_crc=0xDEADBEEF)


def test_decompress_unsupported_method() -> None:
    with pytest.raises(UnsupportedCompression, match="99"):
        decompress(b"data", method=99, expected_size=4, expected_crc=0)


# --- StreamingDecompressor ---


def test_streaming_stored_simple() -> None:
    data = b"Hello, World!"
    crc = zlib.crc32(data) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=0, expected_crc=crc, dest=dest)
    sd.feed(data)
    sd.finish()
    assert dest.getvalue() == data


def test_streaming_stored_empty() -> None:
    data = b""
    crc = zlib.crc32(data) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=0, expected_crc=crc, dest=dest)
    sd.finish()
    assert dest.getvalue() == b""


def test_streaming_stored_binary() -> None:
    data = bytes(range(256))
    crc = zlib.crc32(data) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=0, expected_crc=crc, dest=dest)
    sd.feed(data)
    sd.finish()
    assert dest.getvalue() == data


def test_streaming_stored_chunked() -> None:
    data = b"A" * 1000
    crc = zlib.crc32(data) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=0, expected_crc=crc, dest=dest)
    for pos in range(0, len(data), 100):
        sd.feed(data[pos : pos + 100])
    sd.finish()
    assert dest.getvalue() == data


def test_streaming_deflated_simple() -> None:
    original = b"Hello, World!"
    compressed = zlib.compress(original, level=6)[2:-4]
    crc = zlib.crc32(original) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=8, expected_crc=crc, dest=dest)
    sd.feed(compressed)
    sd.finish()
    assert dest.getvalue() == original


def test_streaming_deflated_repeated() -> None:
    original = b"AAAA" * 1000
    compressed = zlib.compress(original, level=6)[2:-4]
    crc = zlib.crc32(original) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=8, expected_crc=crc, dest=dest)
    sd.feed(compressed)
    sd.finish()
    assert dest.getvalue() == original


def test_streaming_deflated_chunked() -> None:
    original = b"ABCDEFGH" * 500
    compressed = zlib.compress(original, level=6)[2:-4]
    crc = zlib.crc32(original) & 0xFFFFFFFF
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=8, expected_crc=crc, dest=dest)
    for pos in range(0, len(compressed), 100):
        sd.feed(compressed[pos : pos + 100])
    sd.finish()
    assert dest.getvalue() == original


def test_streaming_crc_mismatch() -> None:
    data = b"Hello, World!"
    dest = io.BytesIO()
    sd = StreamingDecompressor(method=0, expected_crc=0xDEADBEEF, dest=dest)
    sd.feed(data)
    with pytest.raises(CRCMismatch):
        sd.finish()


def test_streaming_unsupported_method() -> None:
    dest = io.BytesIO()
    with pytest.raises(UnsupportedCompression, match="99"):
        StreamingDecompressor(method=99, expected_crc=0, dest=dest)
