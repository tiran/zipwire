"""ZipInfo subclass that is fully compatible with stdlib zipfile.ZipInfo."""

from __future__ import annotations

import struct
import typing
import zipfile

from zipwire._constants import ZIP64_EXTRA_FIELD_ID

if typing.TYPE_CHECKING:
    from zipwire._parser import CentralDirEntry


class RemoteZipInfo(zipfile.ZipInfo):
    """A ZipInfo subclass for entries from a remote ZIP archive.

    ``isinstance(info, zipfile.ZipInfo)`` returns True. All standard
    attributes and methods (is_dir, FileHeader, etc.) are available.
    """

    @classmethod
    def _from_central_dir_entry(cls, entry: CentralDirEntry) -> RemoteZipInfo:
        """Construct a ZipInfo from a parsed central directory entry."""
        # Decode filename
        # Bit 11 of flags indicates UTF-8 encoding
        if entry.flags & 0x800:
            filename = entry.filename.decode("utf-8")
        else:
            filename = entry.filename.decode("cp437")

        info = cls(filename)

        # Convert DOS date/time to tuple
        info.date_time = (
            ((entry.mod_date >> 9) & 0x7F) + 1980,  # year
            (entry.mod_date >> 5) & 0x0F,  # month
            entry.mod_date & 0x1F,  # day
            (entry.mod_time >> 11) & 0x1F,  # hour
            (entry.mod_time >> 5) & 0x3F,  # minute
            (entry.mod_time & 0x1F) * 2,  # second
        )

        info.compress_type = entry.compression_method
        info.CRC = entry.crc32
        info.compress_size = entry.compressed_size
        info.file_size = entry.uncompressed_size
        info.header_offset = entry.header_offset
        info.internal_attr = entry.internal_attr
        info.external_attr = entry.external_attr
        info.create_system = (entry.version_made_by >> 8) & 0xFF
        info.create_version = entry.version_made_by & 0xFF
        info.extract_version = entry.version_needed
        info.flag_bits = entry.flags
        info.volume = entry.disk_start
        info.extra = entry.extra
        info.comment = entry.comment

        # Handle ZIP64 extra field
        _apply_zip64_extra(info)

        return info


def _apply_zip64_extra(info: RemoteZipInfo) -> None:
    """Parse ZIP64 extra field and update sizes/offset if present."""
    extra = info.extra
    if not extra:
        return

    offset = 0
    while offset + 4 <= len(extra):
        header_id, data_size = struct.unpack_from("<HH", extra, offset)
        offset += 4

        if header_id == ZIP64_EXTRA_FIELD_ID:
            # ZIP64 extended information extra field
            # Fields appear in order only if the corresponding regular field is 0xFFFFFFFF
            idx = 0
            if info.file_size == 0xFFFFFFFF and idx + 8 <= data_size:
                info.file_size = struct.unpack_from("<Q", extra, offset + idx)[0]
                idx += 8
            if info.compress_size == 0xFFFFFFFF and idx + 8 <= data_size:
                info.compress_size = struct.unpack_from("<Q", extra, offset + idx)[0]
                idx += 8
            if info.header_offset == 0xFFFFFFFF and idx + 8 <= data_size:
                info.header_offset = struct.unpack_from("<Q", extra, offset + idx)[0]
                idx += 8
            if info.volume == 0xFFFF and idx + 4 <= data_size:
                info.volume = struct.unpack_from("<I", extra, offset + idx)[0]
            return

        offset += data_size
