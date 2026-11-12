"""ZIP format constants: signatures, struct formats, and compression methods."""

from __future__ import annotations

import struct
from enum import IntEnum, IntFlag

# ---------------------------------------------------------------------------
# Integer bounds and sentinel values of ZIP fields
# ---------------------------------------------------------------------------
MAX_UINT16 = 0xFFFF
MAX_UINT32 = 0xFFFFFFFF

# ---------------------------------------------------------------------------
# Signatures
# ---------------------------------------------------------------------------
EOCD_SIGNATURE = b"PK\x05\x06"  # zipfile.stringEndArchive
ZIP64_EOCD_LOCATOR_SIGNATURE = b"PK\x06\x07"  # zipfile.stringEndArchive64Locator
ZIP64_EOCD_SIGNATURE = b"PK\x06\x06"  # zipfile.stringEndArchive64
CENTRAL_DIR_SIGNATURE = b"PK\x01\x02"  # zipfile.stringCentralDir
LOCAL_FILE_HEADER_SIGNATURE = b"PK\x03\x04"  # zipfile.stringFileHeader

# ---------------------------------------------------------------------------
# Fixed-part sizes
# ---------------------------------------------------------------------------
EOCD_SIZE = 22  # zipfile.sizeEndCentDir
ZIP64_EOCD_LOCATOR_SIZE = 20  # zipfile.sizeEndCentDir64Locator
ZIP64_EOCD_SIZE = 56  # zipfile.sizeEndCentDir64
CENTRAL_DIR_SIZE = 46  # zipfile.sizeCentralDir
LOCAL_FILE_HEADER_SIZE = 30  # zipfile.sizeFileHeader

# ---------------------------------------------------------------------------
# General purpose bit flags (APPNOTE 4.4.4)
# ---------------------------------------------------------------------------
FLAG_ENCRYPTED = 1 << 0  # zipfile._MASK_ENCRYPTED
FLAG_COMPRESSED_PATCHED_DATA = 1 << 5  # zipfile._MASK_COMPRESSED_PATCH
FLAG_STRONG_ENCRYPTION = 1 << 6  # zipfile._MASK_STRONG_ENCRYPTION
FLAG_UTF8_FILENAME = 1 << 11  # zipfile._MASK_UTF_FILENAME

# ---------------------------------------------------------------------------
# Compression methods
# ---------------------------------------------------------------------------


class CompressionMethod(IntEnum):
    """ZIP compression method identifiers."""

    STORED = 0  # zipfile.ZIP_STORED
    DEFLATED = 8  # zipfile.ZIP_DEFLATED
    BZIP2 = 12  # zipfile.ZIP_BZIP2
    LZMA = 14  # zipfile.ZIP_LZMA
    ZSTANDARD = 93  # zipfile.ZIP_ZSTANDARD (3.14+)


class HeaderFlag(IntFlag):
    """General purpose bit flags of a file header (APPNOTE 4.4.4).

    Single-bit flags only; the multi-bit compression option field
    (bits 1-2) and the reserved bits are omitted.
    """

    ENCRYPTED = 1 << 0
    HAS_DATA_DESCRIPTOR = 1 << 3
    COMPRESSED_PATCHED_DATA = 1 << 5
    STRONG_ENCRYPTION = 1 << 6
    UTF8_FILENAME = 1 << 11
    MASK_HEADER_VALUES = 1 << 13


class ExtraDataId(IntEnum):
    """Extra data field header ids (APPNOTE 4.5)."""

    ZIP64 = 0x0001
    # AV_INFO = 0x0007
    # EXTENDED_LANGUAGE_ENCODING = 0x0008
    # OS2 = 0x0009
    # NTFS = 0x000A
    # OPENVMS = 0x000C
    # PKWARE_UNIX = 0x000D
    # FILE_STREAM_AND_FORK_DESCRIPTORS = 0x000E
    # PATCH_DESCRIPTOR = 0x000F
    # PKCS7 = 0x0014
    # X509_CERT_ID_AND_SIGNATURE_FOR_FILE = 0x0015
    # X509_CERT_ID_FOR_CENTRAL_DIR = 0x0016
    # STRONG_ENCRYPTION_HEADER = 0x0017
    # RECORD_MANAGEMENT_CONTROLS = 0x0018
    # PKCS7_ENC_RECIPIENT_CERT_LIST = 0x0019
    # TIMESTAMP_RECORD = 0x0020
    # POLICY_DECRYPTION_KEY = 0x0021
    # SMARTCRYPT_KEY_PROVIDER = 0x0022
    # SMARTCRYPT_POLICY_KEY_DATA = 0x0023
    # IBM_S390_UNCOMP = 0x0065
    # IBM_S390_COMP = 0x0066
    # POSZIP_4690 = 0x4690
    # EXTENDED_TIMESTAMP = 0x5455
    # BEOS = 0x6542
    # ASI_UNIX = 0x756E
    # INFOZIP_UNIX = 0x7855
    # INFOZIP_UNIX_VAR_SIZE = 0x7875
    # APACHE_COMMONS_COMPRESS = 0xA11E
    # MICROSOFT_OPEN_PACKAGING_GROWTH_HINT = 0xA220
    # SMS_QDOS = 0xFD4A
    # AEX_ENCRYPTION = 0x9901


# ---------------------------------------------------------------------------
# Struct formats
#
# The stdlib defines struct formats too (e.g. zipfile.structCentralDir), but
# they use different field groupings that shift unpack indices.  We define
# our own for cleaner parser code.
# ---------------------------------------------------------------------------

# End of Central Directory Record (22 bytes)
EOCD_STRUCT = struct.Struct(
    "<4s"  # [0] signature
    "H"  # [1] disk_num
    "H"  # [2] disk_cd_start
    "H"  # [3] entries_this_disk
    "H"  # [4] entries_total
    "I"  # [5] cd_size
    "I"  # [6] cd_offset
    "H"  # [7] comment_length
)

# ZIP64 End of Central Directory Locator (20 bytes)
ZIP64_EOCD_LOCATOR_STRUCT = struct.Struct(
    "<4s"  # [0] signature
    "I"  # [1] disk_with_zip64_eocd
    "Q"  # [2] zip64_eocd_offset
    "I"  # [3] total_disks
)

# ZIP64 End of Central Directory Record (56 bytes)
ZIP64_EOCD_STRUCT = struct.Struct(
    "<4s"  # [0] signature
    "Q"  # [1] record_size
    "H"  # [2] version_made
    "H"  # [3] version_needed
    "I"  # [4] disk_num
    "I"  # [5] disk_cd_start
    "Q"  # [6] entries_this_disk
    "Q"  # [7] entries_total
    "Q"  # [8] cd_size
    "Q"  # [9] cd_offset
)

# Central Directory File Header (46 bytes)
CENTRAL_DIR_STRUCT = struct.Struct(
    "<4s"  # [0] signature
    "H"  # [1] version_made
    "H"  # [2] version_needed
    "H"  # [3] flags
    "H"  # [4] compression
    "H"  # [5] mod_time
    "H"  # [6] mod_date
    "I"  # [7] crc32
    "I"  # [8] compressed_size
    "I"  # [9] uncompressed_size
    "H"  # [10] filename_len
    "H"  # [11] extra_len
    "H"  # [12] comment_len
    "H"  # [13] disk_start
    "H"  # [14] internal_attr
    "I"  # [15] external_attr
    "I"  # [16] header_offset
)

# Local File Header (30 bytes)
LOCAL_FILE_HEADER_STRUCT = struct.Struct(
    "<4s"  # [0] signature
    "H"  # [1] version_needed
    "H"  # [2] flags
    "H"  # [3] compression
    "H"  # [4] mod_time
    "H"  # [5] mod_date
    "I"  # [6] crc32
    "I"  # [7] compressed_size
    "I"  # [8] uncompressed_size
    "H"  # [9] filename_len
    "H"  # [10] extra_len
)

# ---------------------------------------------------------------------------
# Derived / misc
# ---------------------------------------------------------------------------
MAX_EOCD_SEARCH = EOCD_SIZE + 65535  # max ZIP comment is 65 535 bytes

ZIP64_EXTRA_FIELD_ID = 0x0001

STREAM_CHUNK_SIZE = 2 * 1024 * 1024  # 2 MiB - default for stream_range backends

# For small files, fetch the local file header and compressed data in a
# single request instead of two.  The extra allowance covers the
# variable-length filename and extra fields in the local header.
PREFETCH_THRESHOLD = 50 * 1024  # 50 KiB
PREFETCH_EXTRA = 1024  # generous allowance for filename + extra fields


def range_header(offset: int, length: int) -> str:
    """Return an HTTP Range header value for an absolute byte range."""
    return f"bytes={offset}-{offset + length - 1}"
