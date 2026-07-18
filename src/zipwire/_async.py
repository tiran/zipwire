"""Asynchronous remote ZIP reader."""

from __future__ import annotations

import typing

from zipwire._constants import (
    LOCAL_FILE_HEADER_SIZE,
    MAX_EOCD_SEARCH,
    PREFETCH_EXTRA,
    PREFETCH_THRESHOLD,
)
from zipwire._decompress import StreamingDecompressor, decompress
from zipwire._errors import FileNotFoundInZip, FileTooLarge, RangeRequestUnsupported
from zipwire._parser import (
    EOCDInfo,
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
        self._eocd: EOCDInfo | None = None

    async def __aenter__(self) -> AsyncRemoteZip:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying reader."""
        await self._reader.close()

    async def get_eocd_info(self) -> EOCDInfo:
        """Return the parsed End of Central Directory record.

        Contains ``cd_offset``, ``cd_size``, and ``cd_entry_count``.
        Triggers lazy loading on first access.
        """
        await self._ensure_loaded()
        assert self._eocd is not None
        return self._eocd

    async def _ensure_loaded(self) -> None:
        """Fetch and parse the central directory if not already done."""
        if self._entries is not None:
            return

        # Step 1: HEAD to get total size, then fetch the tail for EOCD search.
        # We use HEAD + absolute range instead of a single suffix-range
        # request (bytes=-N) because some CDNs, notably Fastly which
        # fronts PyPI, do not support suffix byte ranges and return 501.
        head_headers = await self._reader.head()
        cl = head_headers.get("content-length")
        if cl is None:
            raise RangeRequestUnsupported("Server did not return a Content-Length header")
        self._file_size = int(cl)
        tail_start = max(0, self._file_size - MAX_EOCD_SEARCH)
        tail, _ = await self._reader.read_range(tail_start, self._file_size - tail_start)

        # Step 2: Parse EOCD
        eocd = find_eocd(tail, self._file_size)
        self._eocd = eocd

        # Step 3: Fetch and parse central directory
        cd_data, _ = await self._reader.read_range(eocd.cd_offset, eocd.cd_size)
        raw_entries = parse_central_directory(cd_data, eocd.cd_entry_count)

        # Step 4: Convert to RemoteZipInfo objects
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

    async def _resolve_entry(
        self,
        name: str | RemoteZipInfo,
    ) -> tuple[RemoteZipInfo, int, bytes | None] | None:
        """Resolve *name* to a ZipInfo and compute the compressed data offset.

        Returns ``None`` for directory entries (no data to extract),
        or ``(info, data_offset, prefetched)`` for file entries.
        For small files (compressed size <= 50 KiB) the local header and
        compressed data are fetched in a single request and *prefetched*
        contains the compressed bytes.  Otherwise *prefetched* is ``None``.
        """
        if isinstance(name, RemoteZipInfo):
            info = name
        else:
            info = await self.getinfo(name)
        if info.is_dir():
            return None

        if info.compress_size <= PREFETCH_THRESHOLD:
            # Small file: fetch local header + compressed data in one request.
            fetch_size = LOCAL_FILE_HEADER_SIZE + PREFETCH_EXTRA + info.compress_size
            buf, _ = await self._reader.read_range(info.header_offset, fetch_size)
            local_header = parse_local_file_header(buf)
            data_start = LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
            data_offset = info.header_offset + data_start
            if data_start + info.compress_size <= len(buf):
                return info, data_offset, buf[data_start : data_start + info.compress_size]
            # Rare: variable fields exceeded PREFETCH_EXTRA, fall through
        else:
            buf, _ = await self._reader.read_range(info.header_offset, LOCAL_FILE_HEADER_SIZE)
            local_header = parse_local_file_header(buf)
            data_offset = (
                info.header_offset + LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
            )

        return info, data_offset, None

    async def read(
        self,
        name: str | RemoteZipInfo,
        *,
        max_file_size: int | None = None,
    ) -> bytes:
        """Read and decompress a file from the archive.

        Args:
            name: Filename string or RemoteZipInfo object.
            max_file_size: Optional limit on uncompressed size in bytes.
                Raises :exc:`~zipwire.FileTooLarge` if the entry's
                ``file_size`` exceeds this limit.

        Returns:
            The decompressed file contents.

        .. warning::

            This method loads the entire decompressed file into memory.
            It checks the entry's declared ``file_size`` against
            *max_file_size*, but a crafted archive may lie about its
            uncompressed size.  Use :meth:`read_into` for defence in
            depth: it enforces the size limit during decompression.
        """
        resolved = await self._resolve_entry(name)
        if resolved is None:
            return b""
        info, data_offset, prefetched = resolved
        if max_file_size is not None and info.file_size > max_file_size:
            raise FileTooLarge(info.filename, info.file_size, max_file_size)
        if prefetched is None:
            prefetched, _ = await self._reader.read_range(data_offset, info.compress_size)
        return decompress(
            prefetched,
            info.compress_type,
            info.file_size,
            info.CRC,
        )

    async def read_into(
        self,
        name: str | RemoteZipInfo,
        dest: Writable,
        *,
        max_file_size: int | None = None,
    ) -> None:
        """Decompress a file from the archive into a writable destination.

        Unlike :meth:`read`, this truly streams: the compressed payload is
        fetched in chunks via :meth:`stream_range` and each chunk is
        decompressed and written immediately, keeping peak memory low.

        The streaming decompressor also enforces *max_file_size* during
        decompression, aborting if the actual output exceeds the limit
        regardless of what the entry metadata claims.

        Args:
            name: Filename string or RemoteZipInfo object.
            dest: A writable file-like object (e.g. ``io.BytesIO``, open file).
            max_file_size: Optional limit on uncompressed size in bytes.
                Raises :exc:`~zipwire.FileTooLarge` if the entry's
                ``file_size`` exceeds this limit, or if the actual
                decompressed output exceeds it.
        """
        resolved = await self._resolve_entry(name)
        if resolved is None:
            return
        info, data_offset, prefetched = resolved
        if max_file_size is not None and info.file_size > max_file_size:
            raise FileTooLarge(info.filename, info.file_size, max_file_size)
        sd = StreamingDecompressor(
            info.compress_type,
            info.CRC,
            dest,
            filename=info.filename,
            max_output_size=max_file_size,
        )
        if prefetched is not None:
            sd.feed(prefetched)
        else:
            async for chunk in self._reader.stream_range(data_offset, info.compress_size):
                sd.feed(chunk)
        sd.finish()
