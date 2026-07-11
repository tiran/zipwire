"""Verify RemoteZipInfo is a true subclass of zipfile.ZipInfo."""

from __future__ import annotations

import io
import zipfile

from zipwire._parser import find_eocd, parse_central_directory
from zipwire._zipinfo import RemoteZipInfo


class TestRemoteZipInfoCompat:
    def _get_infos(self, zip_data: bytes) -> list[RemoteZipInfo]:
        eocd = find_eocd(zip_data, len(zip_data))
        cd_data = zip_data[eocd.cd_offset : eocd.cd_offset + eocd.cd_size]
        entries = parse_central_directory(cd_data, eocd.cd_entry_count)
        return [RemoteZipInfo._from_central_dir_entry(e) for e in entries]

    def test_isinstance(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert isinstance(info, zipfile.ZipInfo)
            assert isinstance(info, RemoteZipInfo)

    def test_filename(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        filenames = [info.filename for info in infos]
        assert "hello.txt" in filenames
        assert "data/numbers.bin" in filenames

    def test_date_time(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert len(info.date_time) == 6
            year, month, day, _hour, _minute, _second = info.date_time
            assert 1980 <= year <= 2107
            assert 1 <= month <= 12
            assert 1 <= day <= 31

    def test_compress_type(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert info.compress_type == 0  # STORED

    def test_deflated_compress_type(self, deflated_zip: bytes) -> None:
        infos = self._get_infos(deflated_zip)
        for info in infos:
            assert info.compress_type == 8  # DEFLATED

    def test_sizes(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        hello = next(i for i in infos if i.filename == "hello.txt")
        assert hello.file_size == 13  # len("Hello, World!")
        assert hello.compress_size == 13  # STORED, same size

    def test_crc(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert info.CRC != 0

    def test_is_dir_false(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert not info.is_dir()

    def test_is_dir_true(self, directory_zip: bytes) -> None:
        infos = self._get_infos(directory_zip)
        dir_info = next(i for i in infos if i.filename.endswith("/") and "file" not in i.filename)
        assert dir_info.is_dir()

    def test_unicode_filenames(self, unicode_zip: bytes) -> None:
        infos = self._get_infos(unicode_zip)
        filenames = [info.filename for info in infos]
        assert "\u00e9\u00e0\u00fc.txt" in filenames
        assert "\u4f60\u597d/world.txt" in filenames

    def test_header_offset(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert info.header_offset >= 0

    def test_external_attr(self, stored_zip: bytes) -> None:
        infos = self._get_infos(stored_zip)
        for info in infos:
            assert hasattr(info, "external_attr")

    def test_matches_stdlib(self, stored_zip: bytes) -> None:
        """Verify our RemoteZipInfo matches stdlib's parsing of the same ZIP."""
        our_infos = self._get_infos(stored_zip)
        with zipfile.ZipFile(io.BytesIO(stored_zip)) as zf:
            stdlib_infos = zf.infolist()

        assert len(our_infos) == len(stdlib_infos)
        for ours, stdlib in zip(our_infos, stdlib_infos, strict=True):
            assert ours.filename == stdlib.filename
            assert ours.compress_type == stdlib.compress_type
            assert ours.CRC == stdlib.CRC
            assert ours.file_size == stdlib.file_size
            assert ours.compress_size == stdlib.compress_size
            assert ours.header_offset == stdlib.header_offset
