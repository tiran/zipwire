"""Asynchronous remote ZIP reader."""

from __future__ import annotations

import typing

from zipwire._constants import LOCAL_FILE_HEADER_SIZE
from zipwire._decompress import StreamingDecompressor, decompress
from zipwire._errors import FileNotFoundInZip
from zipwire._parser import (
    eocd_search_length,
    find_eocd,
    parse_central_directory,
    parse_local_file_header,
)
from zipwire._zipinfo import RemoteZipInfo

if typing.TYPE_CHECKING:
    from zipwire._types import AsyncReader, Writable


class AsyncRemoteZip:
    """Read files from a remote ZIP archive using async HTTP range requests.

    Usage::

        async with AsyncRemoteZip(reader) as rz:
            for info in await rz.infolist():
                print(info.filename)
            data = await rz.read("path/to/file.txt")
    """

    def __init__(self, reader: AsyncReader) -> None:
        self._reader = reader
        self._entries: list[RemoteZipInfo] | None = None
        self._name_index: dict[str, RemoteZipInfo] | None = None
        self._file_size: int | None = None

    async def __aenter__(self) -> AsyncRemoteZip:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying reader."""
        await self._reader.close()

    async def _ensure_loaded(self) -> None:
        """Fetch and parse the central directory if not already done."""
        if self._entries is not None:
            return

        # Step 1: Get file size
        self._file_size = await self._reader.get_content_length()

        # Step 2: Fetch the tail for EOCD search
        search_len = eocd_search_length(self._file_size)
        tail_offset = self._file_size - search_len
        tail = await self._reader.read_range(tail_offset, search_len)

        # Step 3: Parse EOCD
        eocd = find_eocd(tail, self._file_size)

        # Step 4: Fetch and parse central directory
        cd_data = await self._reader.read_range(eocd.cd_offset, eocd.cd_size)
        raw_entries = parse_central_directory(cd_data, eocd.cd_entry_count)

        # Step 5: Convert to RemoteZipInfo objects
        self._entries = [RemoteZipInfo._from_central_dir_entry(e) for e in raw_entries]
        self._name_index = {info.filename: info for info in self._entries}

    async def infolist(self) -> list[RemoteZipInfo]:
        """Return a list of RemoteZipInfo objects for all files in the archive."""
        await self._ensure_loaded()
        assert self._entries is not None
        return list(self._entries)

    async def namelist(self) -> list[str]:
        """Return a list of filenames in the archive."""
        await self._ensure_loaded()
        assert self._entries is not None
        return [info.filename for info in self._entries]

    async def getinfo(self, name: str) -> RemoteZipInfo:
        """Return the RemoteZipInfo for the given filename.

        Raises:
            FileNotFoundInZip: If the name is not in the archive.
        """
        await self._ensure_loaded()
        assert self._name_index is not None
        try:
            return self._name_index[name]
        except KeyError:
            raise FileNotFoundInZip(name) from None

    async def read(self, name: str | RemoteZipInfo) -> bytes:
        """Read and decompress a file from the archive.

        Args:
            name: Filename string or RemoteZipInfo object.

        Returns:
            The decompressed file contents.
        """
        if isinstance(name, RemoteZipInfo):
            info = name
        else:
            info = await self.getinfo(name)

        # Directories have no data
        if info.is_dir():
            return b""

        # Step 1: Read the local file header to get the actual data offset
        local_header_data = await self._reader.read_range(
            info.header_offset, LOCAL_FILE_HEADER_SIZE
        )
        local_header = parse_local_file_header(local_header_data)

        # Step 2: Calculate the data offset
        data_offset = (
            info.header_offset + LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
        )

        # Step 3: Fetch the compressed data
        compressed_data = await self._reader.read_range(data_offset, info.compress_size)

        # Step 4: Decompress and verify CRC
        return decompress(
            compressed_data,
            info.compress_type,
            info.file_size,
            info.CRC,
        )

    async def read_into(self, name: str | RemoteZipInfo, dest: Writable) -> None:
        """Decompress a file from the archive into a writable destination.

        Unlike :meth:`read`, this truly streams: the compressed payload is
        fetched in chunks via :meth:`stream_range` and each chunk is
        decompressed and written immediately, keeping peak memory low.

        Args:
            name: Filename string or RemoteZipInfo object.
            dest: A writable file-like object (e.g. ``io.BytesIO``, open file).
        """
        if isinstance(name, RemoteZipInfo):
            info = name
        else:
            info = await self.getinfo(name)

        # Directories have no data
        if info.is_dir():
            return

        # Step 1: Read the local file header to get the actual data offset
        local_header_data = await self._reader.read_range(
            info.header_offset, LOCAL_FILE_HEADER_SIZE
        )
        local_header = parse_local_file_header(local_header_data)

        # Step 2: Calculate the data offset
        data_offset = (
            info.header_offset + LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
        )

        # Step 3: Stream compressed data and decompress into dest
        sd = StreamingDecompressor(info.compress_type, info.CRC, dest)
        async for chunk in self._reader.stream_range(data_offset, info.compress_size):
            sd.feed(chunk)
        sd.finish()
