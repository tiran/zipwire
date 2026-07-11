"""zipwire - Read and extract files from remote ZIP archives over HTTP range requests."""

from __future__ import annotations

from zipwire._async import AsyncRemoteZip
from zipwire._constants import CompressionMethod
from zipwire._errors import (
    BadZipFile,
    CRCMismatch,
    FileNotFoundInZip,
    RangeRequestUnsupported,
    UnsupportedCompression,
    ZipwireError,
)
from zipwire._sync import SyncRemoteZip
from zipwire._types import AsyncReader, SyncReader, Writable
from zipwire._zipinfo import RemoteZipInfo

__all__ = [
    "AsyncReader",
    "AsyncRemoteZip",
    "BadZipFile",
    "CRCMismatch",
    "CompressionMethod",
    "FileNotFoundInZip",
    "RangeRequestUnsupported",
    "RemoteZipInfo",
    "SyncReader",
    "SyncRemoteZip",
    "UnsupportedCompression",
    "Writable",
    "ZipwireError",
]
