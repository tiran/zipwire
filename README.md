# zipwire

Extract individual files from remote ZIP archives over HTTP - without
downloading the whole thing.

A [zip wire](https://en.wikipedia.org/wiki/Zip-line) gets you straight to your
destination. This library does the same: it uses HTTP range requests to fetch
only the central directory and the specific entries you ask for, skipping
everything else. A 10 KB file inside a 2 GB archive? zipwire downloads roughly
10 KB (plus a small overhead for the central directory), not 2 GB.

## How it works

ZIP archives store a central directory at the end of the file that lists every
entry with its offset and size. zipwire fetches that directory first (a single
range request), then makes one additional range request per file you extract.
The server must support `Range` requests (`Accept-Ranges: bytes`), which most
CDNs, object stores, and static file servers do.

## Key features

- **Selective extraction** - download only the files you need, not the entire
  archive.
- **Streaming decompression** - `read_into` decompresses in chunks, keeping
  memory usage low even for large entries.
- **Sync and async** - `SyncRemoteZip` for synchronous code,
  `AsyncRemoteZip` with `await`/`async with` for asyncio.
- **ZIP64** - supports archives and entries larger than 4 GiB.
- **Pluggable backends** - bring your own HTTP library (see below).

## Installation and backends

The default installation includes the **urllib3** backend. To use a different
HTTP library, install the matching extra - for example httpx2 gives you both
sync and async:

```bash
pip install zipwire[httpx2]
```

| Backend  | Class                | Mode  | HTTP    | Install extra |
|----------|----------------------|-------|---------|---------------|
| urllib3  | `Urllib3Reader`      | sync  | 1.1     | *(included)*  |
| httpx2   | `Httpx2SyncReader`   | sync  | 1.1, 2  | `httpx2`      |
| httpx2   | `Httpx2AsyncReader`  | async | 1.1, 2  | `httpx2`      |
| requests | `RequestsReader`     | sync  | 1.1     | `requests`    |
| aiohttp  | `AiohttpReader`      | async | 1.1     | `aiohttp`     |

Every backend accepts an optional pre-configured client or session so you can
share connection pools, authentication, and retry configuration.

## Examples

### Sync - list files and read one

```python
from zipwire import SyncRemoteZip
from zipwire.backends import Urllib3Reader

reader = Urllib3Reader("https://archive.example/data.zip")
with SyncRemoteZip(reader) as rz:
    for info in rz.infolist():
        print(f"{info.filename}  {info.file_size} bytes")

    data = rz.read("path/to/file.txt")
```

### Sync - stream a large file to disk

`read_into` decompresses in chunks so peak memory stays low:

```python
from zipwire import SyncRemoteZip
from zipwire.backends import Urllib3Reader

reader = Urllib3Reader("https://archive.example/large.zip")
with SyncRemoteZip(reader) as rz:
    with open("output.bin", "wb") as f:
        rz.read_into("big-file.bin", f)
```

### Async

```python
import asyncio
from zipwire import AsyncRemoteZip
from zipwire.backends import AiohttpReader

async def main():
    reader = AiohttpReader("https://archive.example/data.zip")
    async with AsyncRemoteZip(reader) as rz:
        data = await rz.read("path/to/file.txt")
        print(data.decode())

asyncio.run(main())
```

## License

Apache-2.0
