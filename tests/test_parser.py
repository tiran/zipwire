"""Unit tests for EOCD, central directory, and local header parsing."""

from __future__ import annotations

import pytest

from zipwire._constants import (
    CENTRAL_DIR_SIZE,
    LOCAL_FILE_HEADER_SIZE,
)
from zipwire._errors import BadZipFile
from zipwire._parser import (
    EOCDInfo,
    find_eocd,
    parse_central_directory,
    parse_local_file_header,
)


class TestFindEocd:
    def test_simple_zip(self, stored_zip: bytes) -> None:
        tail = stored_zip
        eocd = find_eocd(tail, len(stored_zip))
        assert isinstance(eocd, EOCDInfo)
        assert eocd.cd_entry_count == 2
        assert eocd.cd_size > 0
        assert eocd.cd_offset >= 0

    def test_empty_zip(self, empty_zip: bytes) -> None:
        eocd = find_eocd(empty_zip, len(empty_zip))
        assert eocd.cd_entry_count == 0

    def test_zip_with_comment(self, comment_zip: bytes) -> None:
        eocd = find_eocd(comment_zip, len(comment_zip))
        assert eocd.cd_entry_count == 1

    def test_no_eocd_signature(self) -> None:
        with pytest.raises(BadZipFile, match="Could not find"):
            find_eocd(b"\x00" * 100, 100)

    def test_truncated_eocd(self) -> None:
        # EOCD signature but not enough bytes after it
        data = b"PK\x05\x06" + b"\x00" * 10  # Only 14 bytes, need 22
        with pytest.raises(BadZipFile, match="truncated"):
            find_eocd(data, len(data))


class TestParseCentralDirectory:
    def test_stored_zip(self, stored_zip: bytes) -> None:
        eocd = find_eocd(stored_zip, len(stored_zip))
        cd_data = stored_zip[eocd.cd_offset : eocd.cd_offset + eocd.cd_size]
        entries = parse_central_directory(cd_data, eocd.cd_entry_count)
        assert len(entries) == 2
        filenames = [e.filename for e in entries]
        assert b"hello.txt" in filenames
        assert b"data/numbers.bin" in filenames

    def test_entry_fields(self, stored_zip: bytes) -> None:
        eocd = find_eocd(stored_zip, len(stored_zip))
        cd_data = stored_zip[eocd.cd_offset : eocd.cd_offset + eocd.cd_size]
        entries = parse_central_directory(cd_data, eocd.cd_entry_count)

        hello_entry = next(e for e in entries if e.filename == b"hello.txt")
        assert hello_entry.compression_method == 0  # STORED
        assert hello_entry.uncompressed_size == 13  # len("Hello, World!")
        assert hello_entry.crc32 != 0
        assert hello_entry.header_offset >= 0

    def test_truncated_directory(self) -> None:
        # Central dir signature but truncated
        data = b"PK\x01\x02" + b"\x00" * 10
        with pytest.raises(BadZipFile, match="truncated"):
            parse_central_directory(data, 1)

    def test_bad_signature(self) -> None:
        data = b"\x00" * CENTRAL_DIR_SIZE
        with pytest.raises(BadZipFile, match="signature"):
            parse_central_directory(data, 1)


class TestParseLocalFileHeader:
    def test_stored_zip(self, stored_zip: bytes) -> None:
        # The first local header is at offset 0
        header = parse_local_file_header(stored_zip[:LOCAL_FILE_HEADER_SIZE])
        assert header.filename_length == len("hello.txt")
        assert header.data_offset_past_header >= header.filename_length

    def test_truncated_header(self) -> None:
        with pytest.raises(BadZipFile, match="truncated"):
            parse_local_file_header(b"\x00" * 10)

    def test_bad_signature(self) -> None:
        with pytest.raises(BadZipFile, match="signature"):
            parse_local_file_header(b"\x00" * LOCAL_FILE_HEADER_SIZE)
