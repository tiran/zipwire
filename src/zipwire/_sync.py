"""Synchronous remote ZIP reader."""

from __future__ import annotations

import typing

from zipwire._constants import (
    LOCAL_FILE_HEADER_SIZE,
    MAX_EOCD_SEARCH,
    PREFETCH_EXTRA,
    PREFETCH_THRESHOLD,
)
from zipwire._decompress import StreamingDecompressor, decompress
from zipwire._errors import FileNotFoundInZip
from zipwire._parser import (
    find_eocd,
    parse_central_directory,
    parse_local_file_header,
)
from zipwire._zipinfo import RemoteZipInfo

if typing.TYPE_CHECKING:
    from zipwire._types import SyncReader, Writable


class SyncRemoteZip:
    """Read files from a remote ZIP archive using synchronous HTTP range requests.

    Usage::

        with SyncRemoteZip(reader) as rz:
            for info in rz.infolist():
                print(info.filename)
            data = rz.read("path/to/file.txt")
    """

    def __init__(self, reader: SyncReader) -> None:
        self._reader = reader
        self._entries: list[RemoteZipInfo] | None = None
        self._name_index: dict[str, RemoteZipInfo] | None = None
        self._file_size: int | None = None

    def __enter__(self) -> SyncRemoteZip:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying reader."""
        self._reader.close()

    def _ensure_loaded(self) -> None:
        """Fetch and parse the central directory if not already done."""
        if self._entries is not None:
            return

        # Step 1: HEAD to get total size, then fetch the tail for EOCD search.
        # We use HEAD + absolute range instead of a single suffix-range
        # request (bytes=-N) because some CDNs, notably Fastly which
        # fronts PyPI, do not support suffix byte ranges and return 501.
        head_headers = self._reader.head()
        self._file_size = int(head_headers["content-length"])
        tail_start = max(0, self._file_size - MAX_EOCD_SEARCH)
        tail, _ = self._reader.read_range(tail_start, self._file_size - tail_start)

        # Step 2: Parse EOCD
        eocd = find_eocd(tail, self._file_size)

        # Step 4: Fetch and parse central directory
        cd_data, _ = self._reader.read_range(eocd.cd_offset, eocd.cd_size)
        raw_entries = parse_central_directory(cd_data, eocd.cd_entry_count)

        # Step 5: Convert to RemoteZipInfo objects
        self._entries = [RemoteZipInfo._from_central_dir_entry(e) for e in raw_entries]
        self._name_index = {info.filename: info for info in self._entries}

    def infolist(self) -> list[RemoteZipInfo]:
        """Return a list of RemoteZipInfo objects for all files in the archive."""
        self._ensure_loaded()
        assert self._entries is not None
        return list(self._entries)

    def namelist(self) -> list[str]:
        """Return a list of filenames in the archive."""
        self._ensure_loaded()
        assert self._entries is not None
        return [info.filename for info in self._entries]

    def getinfo(self, name: str) -> RemoteZipInfo:
        """Return the RemoteZipInfo for the given filename.

        Raises:
            FileNotFoundInZip: If the name is not in the archive.
        """
        self._ensure_loaded()
        assert self._name_index is not None
        try:
            return self._name_index[name]
        except KeyError:
            raise FileNotFoundInZip(name) from None

    def _resolve_entry(
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
        info = name if isinstance(name, RemoteZipInfo) else self.getinfo(name)
        if info.is_dir():
            return None

        if info.compress_size <= PREFETCH_THRESHOLD:
            # Small file: fetch local header + compressed data in one request.
            fetch_size = LOCAL_FILE_HEADER_SIZE + PREFETCH_EXTRA + info.compress_size
            buf, _ = self._reader.read_range(info.header_offset, fetch_size)
            local_header = parse_local_file_header(buf)
            data_start = LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
            data_offset = info.header_offset + data_start
            if data_start + info.compress_size <= len(buf):
                return info, data_offset, buf[data_start : data_start + info.compress_size]
            # Rare: variable fields exceeded PREFETCH_EXTRA, fall through
        else:
            buf, _ = self._reader.read_range(info.header_offset, LOCAL_FILE_HEADER_SIZE)
            local_header = parse_local_file_header(buf)
            data_offset = (
                info.header_offset + LOCAL_FILE_HEADER_SIZE + local_header.data_offset_past_header
            )

        return info, data_offset, None

    def read(self, name: str | RemoteZipInfo) -> bytes:
        """Read and decompress a file from the archive.

        Args:
            name: Filename string or RemoteZipInfo object.

        Returns:
            The decompressed file contents.
        """
        resolved = self._resolve_entry(name)
        if resolved is None:
            return b""
        info, data_offset, prefetched = resolved
        if prefetched is None:
            prefetched, _ = self._reader.read_range(data_offset, info.compress_size)
        return decompress(
            prefetched,
            info.compress_type,
            info.file_size,
            info.CRC,
        )

    def read_into(self, name: str | RemoteZipInfo, dest: Writable) -> None:
        """Decompress a file from the archive into a writable destination.

        Unlike :meth:`read`, this truly streams: the compressed payload is
        fetched in chunks via :meth:`stream_range` and each chunk is
        decompressed and written immediately, keeping peak memory low.

        Args:
            name: Filename string or RemoteZipInfo object.
            dest: A writable file-like object (e.g. ``io.BytesIO``, open file).
        """
        resolved = self._resolve_entry(name)
        if resolved is None:
            return
        info, data_offset, prefetched = resolved
        sd = StreamingDecompressor(info.compress_type, info.CRC, dest)
        if prefetched is not None:
            sd.feed(prefetched)
        else:
            for chunk in self._reader.stream_range(data_offset, info.compress_size):
                sd.feed(chunk)
        sd.finish()
