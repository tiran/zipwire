"""Read and extract files from remote ZIP archives over HTTP range requests.

Only the central directory and the requested entries are downloaded,
so large archives can be inspected and partially extracted without
fetching the entire file.

Synchronous example
-------------------

::

    from zipwire import SyncRemoteZip
    from zipwire.backends import Urllib3Reader

    reader = Urllib3Reader("https://example.com/archive.zip")
    with SyncRemoteZip(reader) as rz:
        for info in rz.infolist():
            print(f"{info.filename}  {info.file_size} bytes")
        data = rz.read("path/inside/archive.txt")

        # Stream a large entry directly to disk
        with open("local.bin", "wb") as fh:
            rz.read_into("large-file.bin", fh)

Asynchronous example
--------------------

::

    import asyncio
    from zipwire import AsyncRemoteZip
    from zipwire.backends import AiohttpReader

    async def main():
        reader = AiohttpReader("https://example.com/archive.zip")
        async with AsyncRemoteZip(reader) as rz:
            print(rz.namelist())
            data = await rz.read("path/inside/archive.txt")

            # Stream a large entry directly to disk
            with open("local.bin", "wb") as fh:
                await rz.read_into("large-file.bin", fh)

    asyncio.run(main())

Backends
--------

All backends live in :mod:`zipwire.backends` and are lazily imported.

Synchronous:
  - ``Urllib3Reader`` -- default, uses *urllib3*
  - ``RequestsReader`` -- uses *requests* (``pip install zipwire[requests]``)
  - ``Httpx2SyncReader`` -- uses *httpx2*, supports HTTP/2
    (``pip install zipwire[httpx2]``)

Asynchronous:
  - ``AiohttpReader`` -- uses *aiohttp* (``pip install zipwire[aiohttp]``)
  - ``Httpx2AsyncReader`` -- uses *httpx2*, supports HTTP/2
    (``pip install zipwire[httpx2]``)
"""

from __future__ import annotations

from zipwire._async import AsyncRemoteZip
from zipwire._constants import CompressionMethod
from zipwire._errors import (
    BadZipFile,
    CRCMismatch,
    FileNotFoundInZip,
    FileTooLarge,
    RangeRequestUnsupported,
    UnsupportedCompression,
    ZipwireError,
)
from zipwire._parser import EOCDInfo
from zipwire._sync import SyncRemoteZip
from zipwire._types import AsyncReader, Headers, SyncReader, Writable
from zipwire._zipinfo import RemoteZipInfo

__all__ = [
    "AsyncReader",
    "AsyncRemoteZip",
    "BadZipFile",
    "CRCMismatch",
    "CompressionMethod",
    "EOCDInfo",
    "FileNotFoundInZip",
    "FileTooLarge",
    "Headers",
    "RangeRequestUnsupported",
    "RemoteZipInfo",
    "SyncReader",
    "SyncRemoteZip",
    "UnsupportedCompression",
    "Writable",
    "ZipwireError",
]
